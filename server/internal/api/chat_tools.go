// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools.go：agent 领域工具集在 chat 模块的装配——ToolDeps 适配（会话绑定
// 模型解析 / dirty 精确信号 / staged 中途预览信号 / create_project 骨架生成复用）。
// 工具本体与路由守卫见 internal/agent/tools.go；本文件只做 deps 的胶水与锁纪律。
package api

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

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
	p, err := h.deps.Ps.CreateWithKind(title, kind)
	if err != nil {
		return nil, err
	}
	// ifc 管线：建项目即初始化骨架模型（分配 modelId，1 个——script-as-source：
	// 骨架脚本构建出最小 IFC v1）。骨架构建失败 → 回滚项目（不留无模型的 ifc 项目）。
	// cad/cad->ifc 管线：保持空白，agent 会话内经 init_model 工具按需初始化 DXF。
	// ifc / cad->ifc 管线：建项目即初始化 IFC 骨架模型（分配 modelId，绑定——script-as-source：
	// 骨架脚本构建出最小 IFC v1）。cad->ifc 先初始化 ifc 骨架（形成绑定），cad 部分按需
	// 经 init_model 初始化 DXF。骨架构建失败 → 回滚项目。
	// cad 管线：保持空白，agent 会话内经 init_model 按需初始化 DXF。
	if kind == store.KindIFC || kind == "cad->ifc" {
		if _, err := h.initModel(ctx, p.ID, store.KindIFC, title); err != nil {
			_ = h.deps.Ps.Delete(p.ID)
			return nil, fmt.Errorf("初始化 IFC 骨架模型: %w", err)
		}
		// initModel 经 AddModel 更新了 project.json——返回前刷新（p 是 initModel 前旧引用，
		// Models 空会让 REST 响应缺骨架模型）。
		if fresh, err := h.deps.Ps.Get(p.ID); err == nil && fresh != nil {
			return fresh, nil
		}
	}
	return p, nil
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
		InitModel:     h.initModelForAgentTool,
		// D2 项目/方案域
		SessionProject:  h.sessionBoundProject,
		ProjectModels:   h.projectModelsForAgent,
		PlanGet:         h.planGetForAgent,
		PlanDeliver:     h.planDeliverForAgent,
		BuildingDeliver: h.buildingDeliverForAgent,
		SkillWorkDir:    h.skillWorkDirForAgent,
		PlanToWorkdir:   h.planToWorkdirForAgent,
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

// skillWorkDirForAgent 返回项目 skill 工作区绝对路径（{DATA}/skill-work/{projectID}，
// 首次调用 MkdirAll）——aidxf 中间产物（derived/missions/deliver）落盘根，projectId
// 隔离多项目不混淆（复用 plans/{projectID} 的 projectId 隔离地基）。
func (h *ChatHandler) skillWorkDirForAgent(ctx context.Context, projectID string) (string, error) {
	if h.deps.DataDir == "" {
		return "", fmt.Errorf("数据目录未配置")
	}
	dir := filepath.Join(h.deps.DataDir, "skill-work", projectID)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("建 skill 工作区: %w", err)
	}
	return dir, nil
}

// planToWorkdirForAgent 把项目 plan 产物（plan.json + bim_supplement.json）从 PlanStore
// 落到 skill 工作区文件，返回 {planPath, bimPath}——aidxfv3 preprocess --plan <文件> 等
// 命令需要文件路径时的桥接（plan 内容 → 工作区文件）。
func (h *ChatHandler) planToWorkdirForAgent(ctx context.Context, projectID string) (map[string]string, error) {
	if h.deps.PlanSt == nil {
		return nil, fmt.Errorf("方案存储未配置")
	}
	dir, err := h.skillWorkDirForAgent(ctx, projectID)
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for _, name := range []string{"plan.json", "bim_supplement.json"} {
		content, err := h.deps.PlanSt.Get(projectID, name)
		if err != nil {
			return nil, fmt.Errorf("读方案产物 %s: %w", name, err)
		}
		path := filepath.Join(dir, name)
		if err := os.WriteFile(path, content, 0o644); err != nil {
			return nil, fmt.Errorf("写工作区 %s: %w", name, err)
		}
		if name == "plan.json" {
			out["planPath"] = path
		} else {
			out["bimPath"] = path
		}
	}
	return out, nil
}

// planDeliverForAgent 触发 plan 交付（复用 deliverPlan 的 aiplan land 执行逻辑；
// 抽 deliverPlanCore 供 REST handler 与工具共用——单一事实源）。
func (h *ChatHandler) planDeliverForAgent(ctx context.Context, projectID, plan, bimSupplement string) (map[string]any, error) {
	if h.deps.AiplanBin == "" {
		return nil, fmt.Errorf("aiplan 未配置（skill venv 缺失），plan 交付不可用")
	}
	return h.deliverPlanCore(ctx, projectID, []byte(plan), []byte(bimSupplement))
}

// buildingDeliverForAgent 交付 building.json（aidxf S4-c：agent 组装 plan 形态整栋楼 +
// zones 记 modelId）→ PlanStore 版本化 plans/{projectID}/building.json。
// 与 deliver_plan 同构但独立（building 不走 aiplan land——agent 组装直接 Put）。
func (h *ChatHandler) buildingDeliverForAgent(ctx context.Context, projectID, building string) (map[string]any, error) {
	if h.deps.PlanSt == nil {
		return nil, fmt.Errorf("方案存储未配置")
	}
	ver, err := h.deps.PlanSt.Put(projectID, "building.json", []byte(building))
	if err != nil {
		return nil, fmt.Errorf("building.json 版本化: %w", err)
	}
	return map[string]any{"projectId": projectID, "buildingVersion": ver}, nil
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
//
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
