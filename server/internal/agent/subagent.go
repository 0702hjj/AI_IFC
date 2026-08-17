// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// subagent.go：subagent-as-tool 编排——主 agent 经 dispatch_ifc_agent /
// dispatch_cad_agent 工具派发独立子 agent run（深度预算 1：子工具面由
// SubagentConfig.MakeTools 提供，绝不含派发工具，孙代派发结构性不可能）。
// 子事件打 subagentId/parentSessionId 标签经父 Run 的同一事件通道上浮
// （taggedEventHub），EventStore 原样落盘；父会话的 kind 路由/绑定经 ctx
// 继承（子工具解析到父会话 id）。派发工具自身错误文本化（不中断主循环）。
package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync/atomic"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
)

// OrchestratorPersona 是主 agent 的编排者人格（要点取自 skills/aibim-orchestrator
// SKILL.md 意图路由表 + 派发纪律）：主 agent 不直接建模/画图，判断意图 → 派发
// 子 agent → 汇总回报；设计规范/审查问答直接回答不派发。
const OrchestratorPersona = `你是 AI_IFC 平台的设计师对话入口与编排者。你不直接建模/画图：判断意图 → 派生子 Agent → 汇总结果回报设计师。

意图路由：
- IFC 生成/修改（墙、板、层高、构件参数）→ dispatch_ifc_agent；
- DXF 生成/修改（平面、户型、门窗墙体 2D）→ dispatch_cad_agent；
- 设计规范/审查问答 → 直接回答，不派发。

派发纪律：
- dispatch 的 task 必须自包含：子 agent 不见本会话历史——需求要点、显式输入锚点（脚本/模型路径）、期望产物都写进 task；
- 一次一派发，等子 agent 报告再决定下一步；不并行派两个写同一产物的子 agent；
- 子 agent 报告即事实：汇总时原样转述关键字段（产物路径/版本/validate 结果），不编造；
- 破坏性大改（整体重写脚本/删版本）前先用文字向设计师确认。`

// 子 agent persona（要点取自 skills/aibim-orchestrator/references/SUBAGENTS.md，
// 内嵌常量——子 agent 不与设计师对话、不与其他子 agent 交互、按报告格式交付）。
const (
	PersonaIFC = "ifc-agent"
	PersonaCAD = "cad-agent"

	ifcAgentPersona = `你是 IFC 建模子 Agent（技能来源：aiifc skill，script-as-source）。纪律：
- 编辑纪律：先 get_script 读当前脚本，在既有脚本上增量修改，禁止整体重写；保持 PARAMS key 稳定。
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；run 失败先读错误改脚本再重试。
- 不改任何 DXF；不与设计师对话（报告经主 Agent 转述）；不与其他子 Agent 交互；只使用主 Agent 显式给出的输入锚点。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}。`

	cadAgentPersona = `你是 CAD 绘图子 Agent（技能来源：aidxfv skill）。纪律：
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；增量修改既有脚本，禁止整体重写。
- 建筑平面任务对齐 plan 需求逐步生成；产物必须过校验；需要逐实体核查/量测时说明。
- IFC 转换不归你；不与设计师对话（报告经主 Agent 转述）；不与其他子 Agent 交互；只使用主 Agent 显式给出的输入锚点。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}。`
)

// SubagentConfig 是派发工具的依赖包：每次派发新建子模型（NewModel）与
// 子工具面（MakeTools，入参 persona）——并行派发互不共享位置，子工具面
// 绝不含派发工具（深度预算 1）。MaxStep 为子 run 步数上限。
type SubagentConfig struct {
	NewModel  func() model.ToolCallingChatModel
	MakeTools func(persona string) []tool.BaseTool
	MaxStep   int
}

// --- 派发事件上浮通道（父 Run 注入 ctx，子 run 的事件全部打标转发） ---

type ctxKeySubagentHub struct{}

// subagentHub 是子 run → 父事件通道的转发器：为本次父 turn 内每个子 agent
// 分配唯一 subagentId（sa_{turn}_{seq}），把子事件打标后送回父通道。
type subagentHub struct {
	emit   func(Event)     // 父 Run 的原始发送路径（已含 EventStore 落盘）
	parent string          // 父会话 id
	turn   int             // 父 turn 号
	seq    atomic.Int32    // 子 agent 序号（同一 turn 内递增，id 唯一）
	ctx    context.Context // 派发工具的执行 ctx（含父会话绑定）
}

func hubFromContext(ctx context.Context) *subagentHub {
	h, _ := ctx.Value(ctxKeySubagentHub{}).(*subagentHub)
	return h
}

// newSubagentID 生成本次派发的唯一子 id：sa_{parentTurn}_{seq}。
func (h *subagentHub) newSubagentID() string {
	return fmt.Sprintf("sa_%d_%d", h.turn, h.seq.Add(1))
}

// runChild 启动一次子 agent run：事件全部打 subagentId/parentSessionId 标签，
// 经 emit 送回父通道；返回子 agent 的最终答复文本（turn/end 的 message）。
// 子 run 的会话绑定继承父 ctx（SessionIDFromContext 在子工具内仍解析父会话）。
func (h *subagentHub) runChild(ctx context.Context, persona, task string, cfg SubagentConfig) string {
	subID := h.newSubagentID()
	status := func(status string) {
		h.emit(Event{
			Type: EventSubagentStatus, Turn: h.turn, SubagentID: subID, ParentSessionID: h.parent,
			Payload: jsonPayload(map[string]any{
				"subagentId": subID, "parentSessionId": h.parent,
				"persona": persona, "status": status, "task": task,
			}),
		})
	}
	status("started")
	defer status("finished")

	child, err := New(LLMConfig{},
		WithModel(cfg.NewModel()),
		WithTools(cfg.MakeTools(persona)),
		WithPersona(personaPersona(persona)),
		WithMaxStep(cfg.MaxStep),
	)
	if err != nil {
		return fmt.Sprintf("派发失败：创建子 agent 出错：%v", err)
	}
	// 子 run 复用父会话 id：kind 路由 / 会话绑定模型对子工具可用。
	ch, err := child.Run(ctx, h.parent, task)
	if err != nil {
		return fmt.Sprintf("派发失败：%v", err)
	}
	var report string
	for ev := range ch {
		ev.SubagentID = subID
		ev.ParentSessionID = h.parent
		h.emit(ev)
		if ev.Type == EventTurnEnd {
			var p map[string]any
			if len(ev.Payload) > 0 {
				_ = json.Unmarshal(ev.Payload, &p)
			}
			report, _ = p["message"].(string)
		}
	}
	if strings.TrimSpace(report) == "" {
		report = "（子 agent 未产出答复）"
	}
	return report
}

func personaPersona(persona string) string {
	if persona == PersonaCAD {
		return cadAgentPersona
	}
	return ifcAgentPersona
}

type dispatchReq struct {
	Task string `json:"task" jsonschema:"required,description=派发给子 agent 的自包含任务描述（含主 Agent 显式给出的输入锚点/产物路径；子 agent 不见本会话历史）"`
}

// SubagentTools 产出两个派发工具：dispatch_ifc_agent / dispatch_cad_agent。
// 每个工具触发一次独立子 agent run（同步等待子完成，结果 = 子最终报告），
// 子过程事件打标上浮父事件流。深度预算 1：子工具面来自 MakeTools，与
// SubagentTools 的产出结构性隔离。
func SubagentTools(cfg SubagentConfig) []tool.InvokableTool {
	mk := func(name, persona, desc string) tool.InvokableTool {
		return mustTool(name, desc, func(ctx context.Context, in dispatchReq) (string, error) {
			h := hubFromContext(ctx)
			if h == nil {
				return "派发失败：无父会话上下文（派发工具只能在 chat 会话内使用）", nil
			}
			if strings.TrimSpace(in.Task) == "" {
				return "派发失败：task 不能为空——请在 task 里给出自包含的任务描述与输入锚点", nil
			}
			return h.runChild(h.ctx, persona, in.Task, cfg), nil
		})
	}
	return []tool.InvokableTool{
		mk("dispatch_ifc_agent", PersonaIFC,
			"派发 IFC 建模子 agent（aiifc skill，script-as-source：stage→run→save 三段式）。适用于 IFC 生成/修改（墙、板、层高、构件参数）。返回子 agent 最终报告 {产物路径, 版本, validate 结果, 遗留问题}"),
		mk("dispatch_cad_agent", PersonaCAD,
			"派发 CAD 绘图子 agent（aidxfv skill，DXF 生成/校验）。适用于 DXF 生成/修改（平面、户型、门窗墙体 2D）。返回子 agent 最终报告 {产物路径, 版本, validate 结果, 遗留问题}"),
	}
}

// withSubagentHub 把派发转发器注入 ctx（父 Run 启动时调用；工具经
// hubFromContext 解析）。子会话绑定沿用父 ctx（SessionIDFromContext 不变）。
func withSubagentHub(ctx context.Context, h *subagentHub) context.Context {
	return context.WithValue(ctx, ctxKeySubagentHub{}, h)
}
