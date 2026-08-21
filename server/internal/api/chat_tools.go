// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools.go：agent 领域工具集在 chat 模块的装配——ToolDeps 适配（会话绑定
// 模型解析 / dirty 精确信号 / staged 中途预览信号 / create_project 骨架生成复用）。
// 工具本体与路由守卫见 internal/agent/tools.go；本文件只做 deps 的胶水与锁纪律。
package api

import (
	"context"
	"fmt"

	"github.com/cloudwego/eino/components/tool"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/store"
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

// createProjectForAgent 是 create_project 工具的后端（2026-08-20 空白化）：
// 只创建「项目」（空白，不产模型）；kind = 项目类型（ifc|cad|cad→ifc 管线）。
// 会话绑 projectId 后从空白构建（上传计划书 → 对话生成模型）。
func (h *ChatHandler) createProjectForAgent(ctx context.Context, title, kind string) (*store.Project, error) {
	if h.deps.Ps == nil {
		return nil, fmt.Errorf("create_project 未装配（项目聚合缺失）")
	}
	if title == "" {
		title = "AI 项目"
	}
	return h.deps.Ps.CreateWithKind(title, kind)
}

// createProjectForAgentTool 是 agent.ToolDeps.CreateProject 的适配：返回项目信息。
func (h *ChatHandler) createProjectForAgentTool(ctx context.Context, title, kind string) (any, error) {
	p, err := h.createProjectForAgent(ctx, title, kind)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"projectId": p.ID,
		"title":     p.Title,
		"kind":      p.Kind,
		"models":    p.Models,
	}, nil
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
		CreateProject: h.createProjectForAgentTool,
		// D2 项目/方案域
		SessionProject: h.sessionBoundProject,
		ProjectModels:  h.projectModelsForAgent,
		PlanGet:        h.planGetForAgent,
		PlanDeliver:    h.planDeliverForAgent,
	}
}

// sessionBoundProject 解析 ctx 会话绑定的项目 id（A2；无绑定返回 ""）。
func (h *ChatHandler) sessionBoundProject(ctx context.Context) string {
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
		return cs.ProjectID
	}
	return ""
}

// projectModelsForAgent 列项目下模型聚合（经 ProjectStore；项目不存在 → 文本错误）。
func (h *ChatHandler) projectModelsForAgent(ctx context.Context, projectID string) ([]store.ModelRef, error) {
	if h.deps.Ps == nil {
		return nil, fmt.Errorf("项目聚合未配置（store 缺失）")
	}
	p, err := h.deps.Ps.Get(projectID)
	if err != nil {
		return nil, err
	}
	return p.Models, nil
}

// planGetForAgent 读方案产物当前态（经 PlanStore；未配置/缺失 → 文本错误）。
func (h *ChatHandler) planGetForAgent(ctx context.Context, projectID, name string) (string, error) {
	if h.deps.PlanSt == nil {
		return "", fmt.Errorf("方案存储未配置")
	}
	content, err := h.deps.PlanSt.Get(projectID, name)
	if err != nil {
		return "", err
	}
	return string(content), nil
}

// planDeliverForAgent 触发 plan 交付（复用 deliverPlan 的 aiplan land 执行逻辑；
// 抽 deliverPlanCore 供 REST handler 与工具共用——单一事实源）。
func (h *ChatHandler) planDeliverForAgent(ctx context.Context, projectID, plan, bimSupplement string) (map[string]any, error) {
	if h.deps.AiplanBin == "" {
		return nil, fmt.Errorf("aiplan 未配置（skill venv 缺失），plan 交付不可用")
	}
	return h.deliverPlanCore(ctx, projectID, []byte(plan), []byte(bimSupplement))
}

// DomainTools 产出 chat agent 的领域工具集（main 装配：agent.WithTools）。
func (h *ChatHandler) DomainTools() []tool.BaseTool {
	return agent.AsBaseTools(agent.DomainTools(h.AgentToolDeps()))
}

// SetAgent 回填默认 agent（main 装配顺序：handler 先建（工具 deps 需要会话表回调）、
// agent 后建（注入工具）、最后回填引用破环）。启动后不应再改。
func (h *ChatHandler) SetAgent(ag *agent.Agent) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.deps.Ag = ag
}

// SetAgents 回填按项目类型分化的主 agent 集（kind → agent）；启动后不应再改。
func (h *ChatHandler) SetAgents(agents map[string]*agent.Agent) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.deps.Agents = agents
}

// agentForSession 按会话绑定的项目类型路由主 agent：
//   - 项目会话（ProjectID）→ Project.Kind → Agents[kind]；未分化（缺 map/该 kind）落默认 Ag
//   - 模型会话/无绑定 → 默认 Ag
// 历史项目会话（重启后从 chat-sessions.json 恢复）同样按 ProjectID 命中——kind
// 决定 AgentAsTool 选择性装配 + persona + aiplan，会话恢复不落回默认全装。
func (h *ChatHandler) agentForSession(cs *chatSession) *agent.Agent {
	if cs != nil && cs.ProjectID != "" {
		if h.deps.Ps != nil {
			if p, err := h.deps.Ps.Get(cs.ProjectID); err == nil && p != nil && p.Kind != "" {
				if ag := h.deps.Agents[p.Kind]; ag != nil {
					return ag
				}
			}
		}
	}
	return h.deps.Ag
}
