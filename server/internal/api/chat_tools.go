// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools.go：agent 领域工具集在 chat 模块的装配——ToolDeps 适配（会话绑定
// 模型解析 / dirty 精确信号 / staged 中途预览信号 / create_project 骨架生成复用）。
// 工具本体与路由守卫见 internal/agent/tools.go；本文件只做 deps 的胶水与锁纪律。
package api

import (
	"context"
	"fmt"
	"strings"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"

	"ifcviewer/server/internal/agent"
)

// markSessionDirty 把会话置 dirty（变更类工具成功后调用）：notify 不再只靠
// uploads mtime 兜底——工具明确报告了变更落地。持 h.mu 写锁。
func (h *ChatHandler) markSessionDirty(ctx context.Context) {
	sid := agent.SessionIDFromContext(ctx)
	if sid == "" {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if cid, ok := h.byAgent[sid]; ok {
		if cs := h.sessions[cid]; cs != nil {
			cs.dirty = true
		}
	}
}

// pushStaged 是 run_script 工具的中途预览信号适配器：会话解析同 markSessionDirty
// （agentSessionId → chatSessionId），经 pushSystem 推 viewer.staged——载荷严格
// {modelId, kind}，主会话事件（无 subagentId）。pushSystem 自持锁，此处只读解析。
func (h *ChatHandler) pushStaged(ctx context.Context, modelID, kind string) {
	sid := agent.SessionIDFromContext(ctx)
	if sid == "" {
		return
	}
	h.mu.RLock()
	cid, ok := h.byAgent[sid]
	h.mu.RUnlock()
	if !ok {
		return
	}
	h.pushSystem(cid, "viewer.staged", map[string]any{"modelId": modelID, "kind": kind})
}

// sessionBoundModel 解析 ctx 会话绑定的 modelId（agentSessionId → chatSession →
// ModelID）；无绑定返回 ""（工具面提示模型上下文缺失）。
func (h *ChatHandler) sessionBoundModel(ctx context.Context) string {
	sid := agent.SessionIDFromContext(ctx)
	if sid == "" {
		return ""
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	cid, ok := h.byAgent[sid]
	if !ok {
		return ""
	}
	if cs := h.sessions[cid]; cs != nil {
		return cs.ModelID
	}
	return ""
}

// createProjectForAgent 是 create_project 工具的后端：复用 chat 的骨架 IFC 生成
// （createProject handler 的核心三步——骨架内容、St.Create、入队转换），抽出供
// REST 路由与 agent 工具共用；返回可直接 JSON 化的 *store.Model。
func (h *ChatHandler) createProjectForAgent(ctx context.Context, title string) (any, error) {
	if h.deps.St == nil || h.deps.Q == nil {
		return nil, fmt.Errorf("create_project 未装配（store/queue 缺失）")
	}
	if title == "" {
		title = "AI 项目"
	}
	content := skeletonProjectIFC(newGlobalID(), ifcStringEscape(title))
	m, err := h.deps.St.Create(title+".ifc", int64(len(content)), strings.NewReader(content))
	if err != nil {
		return nil, err
	}
	h.deps.Q.Enqueue(m.ID)
	return m, nil
}

// AgentToolDeps 组装 chat agent 的领域工具依赖（main/测试装配共用）。
func (h *ChatHandler) AgentToolDeps() agent.ToolDeps {
	return agent.ToolDeps{
		IFC:           h.deps.Ed,
		CAD:           h.deps.Cad,
		St:            h.deps.St,
		SessionModel:  h.sessionBoundModel,
		MarkDirty:     h.markSessionDirty,
		PushStaged:    h.pushStaged,
		CreateProject: h.createProjectForAgent,
	}
}

// DomainTools 产出 chat agent 的领域工具集（main 装配：agent.WithTools）。
func (h *ChatHandler) DomainTools() []tool.BaseTool {
	return agent.AsBaseTools(agent.DomainTools(h.AgentToolDeps()))
}

// SubagentAgentTools 产出带 subagent 编排的主 agent 工具面（main 装配）：
// 领域工具集 + dispatch_ifc_agent / dispatch_cad_agent。子 agent 工具面 =
// 领域工具集（按 persona 全量提供；kind 路由在工具内部按模型 kind 分流，
// 与主 agent 同一套），绝不含派发工具——深度预算 1 结构性钉死。
// newModel 为 nil 时子模型经 llm 装配（API key 空 → scriptedModel 回退，
// 离线 demo 不派发真推理）；测试可注入 scripted 工厂。
func (h *ChatHandler) SubagentAgentTools(llm agent.LLMConfig, newModel func() model.ToolCallingChatModel) []tool.BaseTool {
	mk := newModel
	if mk == nil {
		mk = func() model.ToolCallingChatModel {
			cm, err := agent.NewChatModel(context.Background(), llm)
			if err != nil || cm == nil {
				return nil // agent.New 回退 scriptedModel
			}
			return cm
		}
	}
	subCfg := agent.SubagentConfig{
		NewModel:  mk,
		MakeTools: func(string) []tool.BaseTool { return h.DomainTools() },
		MaxStep:   agent.DefaultMaxStep,
	}
	return append(h.DomainTools(), agent.AsBaseTools(agent.SubagentTools(subCfg))...)
}

// SetAgent 回填 agent（main 装配顺序：handler 先建（工具 deps 需要会话表回调）、
// agent 后建（注入工具）、最后回填引用破环）。启动后不应再改。
func (h *ChatHandler) SetAgent(ag *agent.Agent) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.deps.Ag = ag
}
