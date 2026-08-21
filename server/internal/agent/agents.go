// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// agents.go：ADK 三角色装配（路线 B，D10 全面迁移）。
//
// orchestrator（主 agent）经官方 AgentAsTool（adk.NewAgentTool）派发 ifc/cad
// 子 agent——子 agent 是独立 ChatModelAgent（Name/Description/各自 persona/
// 独立模型实例/领域工具 + skill middleware），由 orchestrator 的 Tools 装配。
// EmitInternalEvents=true 让子 AgentEvent 实时上浮，翻译层按 RunPath 合成
// subagentId 标签与 subagent/status（见 events.go §4）。
//
// orchestrator 特殊性（D11）：它是唯一对话入口，aiplan/aibim-orchestrator
// 的对话协调层内联在 orchestrator（skill middleware 全量挂载，模型可加载
// aiplan 规划流程 + aibim-orchestrator 编排手册）；子 agent 各自挂领域 skill
// （aiifc / aidxf，当前为全量目录，角色化过滤留后续精化）。
package agent

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"github.com/cloudwego/eino/adk"
	localbk "github.com/cloudwego/eino-ext/adk/backend/local"
	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/schema"

	"github.com/cloudwego/eino/adk/middlewares/skill"

	fsmw "github.com/cloudwego/eino/adk/middlewares/filesystem"
)

// OrchestratorPersona 是主 agent 的编排者人格（要点取自 skills/aibim-orchestrator
// SKILL.md 意图路由表 + 派发纪律）：主 agent 不直接建模/画图，判断意图 → 派发
// 子 agent → 汇总回报；设计规范/审查问答直接回答不派发。
//
// 路由纪律（第一层：意图 × skill 组合）：
//   - CAD/DXF 生成修改 → **必须先加载 aiplan** 与用户对话框定方案，再派 cad-agent（强前置）
//   - IFC 生成修改 → 直接派 ifc-agent（独立，不经 aiplan；ifc↔dxf 产物未对接，两条线独立）
//   - 模糊想法/完整方案 → aiplan → cad →（ifc 可选，全链）
//   - 设计规范/审查问答 → 直接回答，不派发
// OrchestratorPersona 是 cad->ifc 项目的编排者人格（全装：aiplan + cad + ifc——
// cad->ifc 管线需要三个都装）。**kind 强制必选（create_project 强制 ifc|cad|cad->ifc，
// 无空 kind）**——orchestrator 按 kind 强制装配：cad→personaCAD、ifc→personaIFC、
// cad->ifc→OrchestratorPersona（本 persona，专用于 cad->ifc 全链编排）。
const OrchestratorPersona = `你是 AI_IFC 平台的设计师对话入口与编排者（cad->ifc 项目，全链：plan → cad → ifc）。你不直接建模/画图：判断意图 → 派生子 Agent → 汇总结果回报设计师。

编排契约（cad->ifc 全链步骤——每步产物锚点 + 断点主持明确）：
- ① plan：加载 aiplan skill 与设计师对话框定建筑方案（4 轮渐进，断点 ask_user 你主持：设计方向/缺口/确认）→ deliver_plan 交付 plan.json + bim_supplement.json（PlanStore 版本化）。
- ② cad：派 cad-agent（request 带 plan 锚点：提示先 stage_plan_to_workdir 拿 plan 文件路径跑 aidxfv3 --plan，S0-S4 出图）→ cad 逐 zone init_model 注册平台模型（modelId）→ deliver_building 交付 building.json（zones 记 modelId）。
- ③ ifc：派 ifc-agent **消费上游路径**（workflows/CONSUME_UPSTREAM.md，request 指定 + 带上游锚点：building.json + bim_supplement.json + 各 zone DXF modelId）→ ifc 在已绑定骨架（create_project(cad->ifc) 已 init_model 绑定）上深化 → IFC 交付。
- 设计规范/审查问答 → 直接回答，不派发。

产物传递锚点（步骤间的产物怎么传——写进子 agent request）：
- aiplan → cad：plan.json + bim_supplement.json（deliver_plan 落 PlanStore；cad 经 stage_plan_to_workdir 拿文件路径跑 aidxfv3 --plan）；
- cad → ifc：building.json（deliver_building 落 PlanStore，zones 记 modelId）+ 各 zone DXF 平台模型（init_model 的 modelId）+ bim_supplement.json（ifc 经 get_project_plans 读 building + bim，经 modelId 拿 DXF）。

派发纪律：
- 子 agent 的 request 必须自包含：子 agent 不见本会话历史——需求要点、显式输入锚点（plan/脚本/模型路径/modelId）、期望产物都写进 request；
- 一次一派发，等子 agent 报告再决定下一步；不并行派两个写同一产物的子 agent；
- 子 agent 报告即事实：汇总时原样转述关键字段（产物路径/modelId/版本/validate 结果），不编造；
- 破坏性大改（整体重写脚本/删版本）前先用文字向设计师确认。

断点主持（HITL ask_user）：plan 4 轮设计对话（aiplan）与 aidxf ⓪①② 断点由子 agent 弹框（ask_user），你汇总断点结论转述设计师。

plan 工作区（aiplan 你亲自跑时）：aiplan 的 route/land 等命令加 --project-id <会话绑定 projectID>——CLI 内部自动算 skill-work/{projectID}/aiplan/ 落盘（结构性保证，不用你传 workspace 路径）；交付 deliver_plan 走工具（PlanStore 版本化）。`


// OrchestratorPersonaCAD 是 CAD 项目的编排者人格（cad 管线）：只派 cad-agent，
// aiplan 前置框定方案；无 IFC 分支。
const personaCAD = `你是 AI_IFC 平台的设计师对话入口与编排者（CAD 项目）。你不直接建模/画图：判断意图 → 派发 cad-agent → 汇总结果回报设计师。

编排契约（cad 管线步骤——每步产物锚点 + 断点主持明确）：
- ① plan：加载 aiplan skill 与设计师对话框定建筑方案（4 轮渐进：骨架→几何→功能→结构空间，断点 ask_user 你主持：设计方向/缺口/确认）→ deliver_plan 交付 plan.json + bim_supplement.json（PlanStore 版本化）。无 plan 不派 cad（强前置）。
- ② cad：派 cad-agent（request 带 plan 锚点：提示先 stage_plan_to_workdir 拿 plan 文件路径跑 aidxfv3 --plan，S0-S4 出图）→ cad 逐 zone init_model 注册平台模型（modelId）→ deliver_building 交付 building.json（zones 记 modelId）→ 交付。
- 设计规范/审查问答 → 直接回答，不派发。

产物传递锚点：aiplan → cad = plan.json + bim_supplement.json（deliver_plan 落 PlanStore；cad 经 stage_plan_to_workdir 拿文件路径）。

断点主持（HITL ask_user）：plan 4 轮设计对话与 aidxf ⓪①② 断点由你/子 agent 弹框，汇总断点结论转述设计师。

派发纪律：
- 子 agent 的 request 必须自包含：子 agent 不见本会话历史——需求要点、显式输入锚点（plan/脚本/模型路径/modelId）、期望产物都写进 request；
- 一次一派发，等子 agent 报告再决定下一步；
- 子 agent 报告即事实：汇总时原样转述关键字段（产物路径/modelId/版本/validate 结果），不编造；
- 破坏性大改（整体重写脚本/删版本）前先用文字向设计师确认。`

// OrchestratorPersonaIFC 是 IFC 项目的编排者人格（ifc 管线）：只派 ifc-agent，
// 不经 aiplan（IFC 与 CAD 独立）；无 CAD 分支。
const personaIFC = `你是 AI_IFC 平台的设计师对话入口与编排者（IFC 项目）。你不直接建模/画图：判断意图 → 派发 ifc-agent → 汇总结果回报设计师。

编排契约（ifc 独立管线步骤——产物锚点 + 断点主持明确）：
- ① 派 ifc-agent **design.json 前置路径**（workflows/PLAN_DXF_IFC.md，request 指定）：复杂平面先产 design.json 框定设计意图（纯语义，无坐标），断点 ask_user 你主持确认设计意图 → ifc-agent 在已绑定骨架上深化（init_model(ifc) 建项目已绑定骨架）→ ② IFC 交付（scripts/v{n}.py + versions/v{n}.ifc + XKT）。
- 设计规范/审查问答 → 直接回答，不派发。

产物锚点：ifc 骨架 modelId（create_project(ifc) 建项目已 init_model 绑定）——ifc-agent 在骨架上深化。

断点主持（HITL ask_user）：design.json 设计意图确认由你主持（ifc 独立管线无 aiplan，aiifc 自己框定设计）。

派发纪律：
- 子 agent 的 request 必须自包含：子 agent 不见本会话历史——需求要点、显式输入锚点（脚本/模型路径/modelId）、期望产物都写进 request；
- 一次一派发，等子 agent 报告再决定下一步；
- 子 agent 报告即事实：汇总时原样转述关键字段（产物路径/modelId/版本/validate 结果），不编造；
- 破坏性大改（整体重写脚本/删版本）前先用文字向设计师确认。`

// 子 agent persona（要点取自 skills/aibim-orchestrator/references/SUBAGENTS.md，
// 内嵌常量——子 agent 不与设计师对话、不与其他子 agent 交互、按报告格式交付）。
const (
	PersonaIFC = "ifc-agent"
	PersonaCAD = "cad-agent"

	ifcAgentPersona = `你是 IFC 建模子 Agent（技能来源：aiifc skill，script-as-source）。纪律：
- **深化路径由主 Agent 指定**（你不自己判断）：主 Agent 指定消费上游路径 → 走 workflows/CONSUME_UPSTREAM.md（get_project_plans 读 bim_supplement + building.json，经 zones[].modelId 拿各 zone DXF，在已绑定骨架上深化，不产 design.json）；主 Agent 指定 design.json 前置路径 → 走 workflows/PLAN_DXF_IFC.md（复杂平面先产 design.json 框定设计供确认，再从零建模）。
- 编辑纪律：先 get_script 读当前脚本，在既有脚本上增量修改，禁止整体重写；保持 PARAMS key 稳定。
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；run 失败先读错误改脚本再重试。
- 不改任何 DXF；不与设计师对话（报告经主 Agent 转述）；不与其他子 Agent 交互；只使用主 Agent 显式给出的输入锚点。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}。`

	cadAgentPersona = `你是 CAD 绘图子 Agent（技能来源：aidxf skill，plan 产物消费 aiplan）。纪律：
- **先消费 plan 再动手**：执行前必须先 get_project_plans 读 plan.json + bim_supplement.json，严格按 plan 的户型/分区/面积/层高/建筑语言生成；plan 缺失或与需求不符时向主 Agent 报告，禁止无 plan 硬画。
- **工作目录必须先取后用**：动手画之前先 aidxfv3 init --project-id <会话绑定 projectID>（或 get_skill_workdir 拿路径）建 skill 工作区（skill-work/{projectID}，projectId 隔离），后续所有 aidxfv3 命令加 --project-id <projectID>——CLI 内部自动算 skill-work/{projectID} 落盘（结构性保证，不用你传 --project 路径）；中间产物（derived/missions/deliver）落该工作区，禁止落到其他位置（避免多项目混淆/游离文件）。
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；增量修改既有脚本，禁止整体重写。
- 产物必须过校验；需要逐实体核查/量测时说明。
- IFC 转换不归你；不与设计师对话（报告经主 Agent 转述）；不与其他子 Agent 交互；只使用主 Agent 显式给出的输入锚点。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}。`
)

// newSkillMiddleware 构造官方 skill middleware（ch09 同构：local backend →
// skill backend 扫 BaseDir/*/SKILL.md → NewTyped）。skillsDir 为空返回 nil。
// allow 非空时按角色过滤：模型工具面只出现允许的 skill（第一层：角色映射）。
func newSkillMiddleware(ctx context.Context, skillsDir string, allow ...string) (adk.TypedChatModelAgentMiddleware[*schema.Message], error) {
	if skillsDir == "" {
		return nil, nil
	}
	backend, err := localbk.NewBackend(ctx, &localbk.Config{})
	if err != nil {
		return nil, fmt.Errorf("create local backend: %w", err)
	}
	skillBackend, err := skill.NewBackendFromFilesystem(ctx, &skill.BackendFromFilesystemConfig{
		Backend: backend,
		BaseDir: skillsDir,
	})
	if err != nil {
		return nil, fmt.Errorf("create skill backend: %w", err)
	}
	if len(allow) > 0 {
		skillBackend = &filteredSkillBackend{inner: skillBackend, allow: toSet(allow)}
	}
	skillMW, err := skill.NewTyped[*schema.Message](ctx, &skill.TypedConfig[*schema.Message]{
		Backend: skillBackend,
	})
	if err != nil {
		return nil, fmt.Errorf("create skill middleware: %w", err)
	}
	return skillMW, nil
}

// filteredSkillBackend 是 skill.Backend 的角色过滤薄包装：
// List 只返回允许集内的 skill（工具描述只显示本角色可用的）；
// Get 拒绝允许集外的调用（模型调别的 skill → 文本错误，不中断循环）。
type filteredSkillBackend struct {
	inner skill.Backend
	allow map[string]bool
}

func toSet(names []string) map[string]bool {
	m := make(map[string]bool, len(names))
	for _, n := range names {
		m[n] = true
	}
	return m
}

func (b *filteredSkillBackend) List(ctx context.Context) ([]skill.FrontMatter, error) {
	all, err := b.inner.List(ctx)
	if err != nil {
		return nil, err
	}
	out := all[:0]
	for _, fm := range all {
		if b.allow[fm.Name] {
			out = append(out, fm)
		}
	}
	return out, nil
}

func (b *filteredSkillBackend) Get(ctx context.Context, name string) (skill.Skill, error) {
	if !b.allow[name] {
		return skill.Skill{}, fmt.Errorf("skill 不属于当前角色（仅允许 %s）：%s", keysOf(b.allow), name)
	}
	return b.inner.Get(ctx, name)
}

func keysOf(m map[string]bool) string {
	var names []string
	for k := range m {
		names = append(names, k)
	}
	sort.Strings(names)
	return strings.Join(names, "/")
}

// newFilesystemMiddleware 构造收敛版官方 filesystem middleware（M2-0/D12）：
//   - Backend = 只读包装（读 skill references 透传，Write/Edit 拒绝——领域收敛）
//   - StreamingShell = local backend + ValidateCommand 命令白名单（aiplan/aidxfv3）
//
// 模型由此获得：read_file/glob/grep/ls（读 skill 包内文件）+ execute（跑 skill CLI）。
func newFilesystemMiddleware(ctx context.Context) (adk.TypedChatModelAgentMiddleware[*schema.Message], error) {
	backend, err := localbk.NewBackend(ctx, &localbk.Config{
		ValidateCommand: validateSkillCommand, // 命令白名单（领域收敛单点）
	})
	if err != nil {
		return nil, fmt.Errorf("create local backend: %w", err)
	}
	mw, err := fsmw.NewTyped[*schema.Message](ctx, &fsmw.MiddlewareConfig{
		Backend:        &fsReadOnlyBackend{inner: backend}, // 读透传 / 写拒绝
		StreamingShell: backend,                             // execute + 白名单
	})
	if err != nil {
		return nil, fmt.Errorf("create filesystem middleware: %w", err)
	}
	return mw, nil
}

// roleAgentConfig 是子 agent（被 AgentAsTool 派发的角色）装配参数。
type roleAgentConfig struct {
	name        string
	description string
	instruction string
	model       model.ToolCallingChatModel
	tools       []tool.BaseTool
	skillsDir   string
	skills      []string // 本角色允许的 skill 名（角色化过滤，第一层）；空 = 不挂 skill
	maxStep     int
}

// newRoleAgent 构造一个角色子 agent：独立 ChatModelAgent（Name/Description/
// Instruction/独立模型实例）+ 领域工具 + 角色 skill middleware + filesystem middleware
// + 工具错误兜底。不含 AgentAsTool——深度预算 1 结构性保证（子 agent 无派发工具）。
func newRoleAgent(ctx context.Context, cfg roleAgentConfig) (adk.Agent, error) {
	var handlers []adk.TypedChatModelAgentMiddleware[*schema.Message]
	if cfg.skillsDir != "" && len(cfg.skills) > 0 {
		skillMW, err := newSkillMiddleware(ctx, cfg.skillsDir, cfg.skills...)
		if err != nil {
			return nil, err
		}
		handlers = append(handlers, skillMW)
	}
	fsMW, err := newFilesystemMiddleware(ctx)
	if err != nil {
		return nil, err
	}
	handlers = append(handlers, fsMW)
	handlers = append(handlers, newSafeToolMiddleware())
	ag, err := adk.NewChatModelAgent(ctx, &adk.ChatModelAgentConfig{
		Name:          cfg.name,
		Description:   cfg.description,
		Instruction:   cfg.instruction,
		Model:         cfg.model,
		MaxIterations: cfg.maxStep,
		ToolsConfig: adk.ToolsConfig{ToolsNodeConfig: compose.ToolsNodeConfig{
			Tools: cfg.tools,
		}},
		Handlers: handlers,
	})
	if err != nil {
		return nil, fmt.Errorf("create role agent %s: %w", cfg.name, err)
	}
	return ag, nil
}

// kindChildren 按项目类型选择 AgentAsTool 子 agent：
//   cad->ifc/空（全装）→ cad + ifc；cad → 只 cad；ifc → 只 ifc。
func kindChildren(kind string, cad, ifc adk.Agent) []adk.Agent {
	var out []adk.Agent
	if kind != "ifc" {
		out = append(out, cad)
	}
	if kind != "cad" {
		out = append(out, ifc)
	}
	return out
}

// orchestratorTools 把子 agent 包装为官方 AgentAsTool 并追加到父工具面。
func orchestratorTools(tools []tool.BaseTool, children ...adk.Agent) []tool.BaseTool {
	out := make([]tool.BaseTool, 0, len(tools)+len(children))
	out = append(out, tools...)
	for _, child := range children {
		out = append(out, adk.NewAgentTool(context.Background(), child))
	}
	return out
}
