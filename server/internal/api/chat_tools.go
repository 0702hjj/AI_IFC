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

// createProjectForAgent 是 create_project 工具的后端（A1 项目级）：创建「项目」
// （projectID）+ 首交付模型（kind 可选 ifc/dxf）。单 kind = 项目下主交付模型；
// 管线（dxf→ifc）后续模型经 AddModel 挂入同一 projectID。返回 (model, project)。
// Ps 未配置时降级单模型（返回 project=nil，调用方按兼容处理）。
func (h *ChatHandler) createProjectForAgent(ctx context.Context, title, kind string) (*store.Model, *store.Project, error) {
	if h.deps.St == nil || h.deps.Q == nil {
		return nil, nil, fmt.Errorf("create_project 未装配（store/queue 缺失）")
	}
	if title == "" {
		title = "AI 项目"
	}
	if !store.ValidKind(kind) {
		return nil, nil, fmt.Errorf("create_project 不支持 kind=%q（ifc|dxf）", kind)
	}
	var m *store.Model
	var err error
	if kind == store.KindDXF {
		m, err = h.deps.St.CreateWithKind(title+".dxf", int64(len(skeletonDXF)), strings.NewReader(skeletonDXF), store.KindDXF)
	} else {
		content := skeletonProjectIFC(newGlobalID(), ifcStringEscape(title))
		m, err = h.deps.St.Create(title+".ifc", int64(len(content)), strings.NewReader(content))
	}
	if err != nil {
		return nil, nil, err
	}
	h.deps.Q.Enqueue(m.ID)
	// 项目聚合（Ps 未配置：降级单模型——旧装配兼容）
	if h.deps.Ps == nil {
		return m, nil, nil
	}
	p, err := h.deps.Ps.Create(title)
	if err != nil {
		return nil, nil, err
	}
	if err := h.deps.Ps.AddModel(p.ID, m.ID, m.Kind, m.Name, m.Status); err != nil {
		return nil, nil, err
	}
	return m, p, nil
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
	}
}

// createProjectForAgentTool 是 agent.ToolDeps.CreateProject 的适配（项目级 A1）：
// 返回可 JSON 化的 {model, project}。kind 缺省 ifc。
func (h *ChatHandler) createProjectForAgentTool(ctx context.Context, title, kind string) (any, error) {
	if kind == "" {
		kind = store.KindIFC
	}
	m, p, err := h.createProjectForAgent(ctx, title, kind)
	if err != nil {
		return nil, err
	}
	if p == nil { // Ps 未配置：降级单模型（旧装配）
		return m, nil
	}
	return map[string]any{
		"modelId":   m.ID,
		"projectId": p.ID,
		"title":     p.Title,
		"kind":      m.Kind,
		"models":    p.Models,
	}, nil
}

// DomainTools 产出 chat agent 的领域工具集（main 装配：agent.WithTools）。
func (h *ChatHandler) DomainTools() []tool.BaseTool {
	return agent.AsBaseTools(agent.DomainTools(h.AgentToolDeps()))
}

// SetAgent 回填 agent（main 装配顺序：handler 先建（工具 deps 需要会话表回调）、
// agent 后建（注入工具）、最后回填引用破环）。启动后不应再改。
func (h *ChatHandler) SetAgent(ag *agent.Agent) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.deps.Ag = ag
}
