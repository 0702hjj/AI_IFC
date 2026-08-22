// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// init_model.go：模型初始化（agent 会话内新建模型的统一链路）。
// script-as-source 初始化：分配 modelId（store 生成）→ 骨架脚本 stage → run 沙箱构建
// → save v1 → 模型 ready（ifc 排队 XKT / dxf 直 ready）。骨架内容对齐旧 skeletonIFC/DXF：
//   IFC：IfcProject + 几何上下文 + 单位；DXF：空图纸。
// kind 分化（2026-08-21 方案确认）：
//   - ifc：create_project 建立时即初始化骨架模型（本辅助在 create_project 内调）
//   - dxf：create_project 空白；agent 每次新建 DXF 时 init_model（本辅助由工具调）
package api

import (
	"context"

	"ifcviewer/server/internal/agent"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"ifcviewer/server/internal/store"
)

// verifyInitModelKind 校验 init 模型 kind 与项目 kind 匹配（verify 层单点，业务规则）。
// 项目 kind 必填（create_project 强制 ifc|cad|cad->ifc）：
//   cad 项目只能初始化 dxf 模型（IFC 属 ifc 管线，cad 项目不该有 ifc）；
//   ifc 项目只能初始化 ifc 模型；
//   cad->ifc 两者都可（cad 先 dxf，ifc 后 ifc，按需）。
func verifyInitModelKind(projectKind, initKind string) error {
	if initKind != store.KindIFC && initKind != store.KindDXF {
		return fmt.Errorf("init kind 仅支持 ifc/dxf，got %q", initKind)
	}
	switch projectKind {
	case "cad":
		if initKind != store.KindDXF {
			return fmt.Errorf("cad 项目只能初始化 dxf 模型（ifc 属 ifc 管线，cad 项目不该有 ifc）")
		}
	case "ifc":
		if initKind != store.KindIFC {
			return fmt.Errorf("ifc 项目只能初始化 ifc 模型（dxf 属 cad 管线，ifc 项目不该有 dxf）")
		}
	case "cad->ifc":
		// 两者都可（cad 先 dxf，ifc 后 ifc，按需）
	}
	return nil
}


// initModel 初始化一个骨架模型（script-as-source：骨架脚本构建出最小模型 v1）。
//
// 返回：*store.Model（含分配的 modelId）。失败回滚模型记录（骨架构建失败不留空模型）。
func (h *ChatHandler) initModel(ctx context.Context, projectID, kind, title string) (*store.Model, error) {
	// init_model 必须在项目会话里（项目绑定唯一会话，A2）；项目 kind 必填（create_project 强制）。
	if projectID == "" || h.deps.Ps == nil {
		return nil, fmt.Errorf("init_model 需项目绑定（会话未绑项目/项目存储未配置）")
	}
	p, err := h.deps.Ps.Get(projectID)
	if err != nil || p == nil {
		return nil, fmt.Errorf("项目不存在: %s", projectID)
	}
	// kind 缺省按项目 kind 推导：cad→dxf、ifc→ifc、cad->ifc→dxf（cad 先）。
	if kind == "" {
		if p.Kind == "ifc" {
			kind = store.KindIFC
		} else { // cad / cad->ifc 默认 dxf（cad 先）
			kind = store.KindDXF
		}
	}
	// 项目 kind 约束（verify 层）：cad 项目只能 dxf、ifc 项目只能 ifc、cad->ifc 两者都可。
	if err := verifyInitModelKind(p.Kind, kind); err != nil {
		return nil, err
	}
	skelScript := skeletonIFCScript
	storeKind := store.KindIFC
	if kind == store.KindDXF {
		skelScript = skeletonDXFScript
		storeKind = store.KindDXF
	}
	if h.deps.St == nil {
		return nil, fmt.Errorf("model store 未配置")
	}
	// 骨架脚本填 title（JSON 安全字符串，防引号破坏 Python dict 字面量）
	titleJSON, _ := json.Marshal(title)
	script := strings.ReplaceAll(skelScript, `{"title": "{title}"}`, `{"title": `+string(titleJSON)+`}`)

	// 1. 创建模型记录（分配 modelId；骨架构建前空文件占位，kind 决定初始 status）
	//    用 CreateWithKindInProject 写 Model.ProjectID 反向归属（A1：项目下模型）。
	m, err := h.deps.St.CreateWithKindInProject(title, 0, strings.NewReader(""), storeKind, projectID)
	if err != nil {
		return nil, fmt.Errorf("创建模型记录: %w", err)
	}
	cl := h.deps.editClientForKind(m)
	if cl == nil {
		return nil, fmt.Errorf("kind=%s 编辑后端未配置（services/%s 未起）", storeKind, map[string]string{store.KindIFC: "ifc", store.KindDXF: "cad"}[storeKind])
	}

	// 骨架构建失败回滚：不留空模型（脚本契约/沙箱错误会 422）。
	rollback := func(cause error) (*store.Model, error) {
		_ = h.deps.St.Delete(m.ID)
		return nil, cause
	}

	// 2. stage 骨架脚本（全量替换，不执行）
	body, _ := json.Marshal(map[string]string{"script": script, "note": "init skeleton"})
	if _, err := cl.Do(ctx, http.MethodPut, "/models/"+m.ID+"/script", body); err != nil {
		return rollback(fmt.Errorf("stage 骨架脚本: %w", err))
	}
	// 3. run_script 沙箱构建（骨架脚本 → 模型文件）
	if _, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+m.ID+"/script/run", nil); err != nil {
		return rollback(fmt.Errorf("沙箱构建骨架: %w", err))
	}
	// 4. save_script 落 v1 版本（骨架即 v1）
	saveBody, _ := json.Marshal(map[string]string{"note": "init skeleton v1"})
	if _, err := cl.DoSlow(ctx, http.MethodPost, "/models/"+m.ID+"/script/save", saveBody); err != nil {
		return rollback(fmt.Errorf("落 v1 版本: %w", err))
	}

	// 5. 挂到项目（projectID 非空时；D13 后 agent 经 init_model 挂 Project.Models）。
	//    挂项目失败 → 回滚模型（不留孤儿：模型必须归属项目，A1）。
	if projectID != "" && h.deps.Ps != nil {
		if err := h.deps.Ps.AddModel(projectID, m.ID, storeKind, title, "ready"); err != nil {
			_ = h.deps.St.Delete(m.ID)
			return nil, fmt.Errorf("挂到项目: %w", err)
		}
	}

	// 6. ifc kind 排队 XKT 重转（dxf 无 XKT 产物，render.json 直挂）。
	if storeKind == store.KindIFC && h.deps.Q != nil {
		h.deps.Q.EnqueueIfStale(m.ID)
	}
	return m, nil
}

// initModelForAgentTool 是 agent.ToolDeps.InitModel 的适配：返回可 JSON 化的模型信息。
// 成功后推 model.created SSE 事件——前端刷新项目模型列表 + 渲染新模型（agent 生成链路）。
func (h *ChatHandler) initModelForAgentTool(ctx context.Context, projectID, kind, title string) (any, error) {
	m, err := h.initModel(ctx, projectID, kind, title)
	if err != nil {
		return nil, err
	}
	// 推 model.created：会话订阅者收到后刷新项目模型列表/渲染（viewer.staged 同源链路）。
	if cid := h.chatSessionIDFromAgent(ctx); cid != "" {
		h.pushSystem(cid, "model.created", map[string]any{
			"modelId": m.ID, "kind": m.Kind, "title": m.Name, "projectId": projectID,
		})
	}
	return map[string]any{
		"modelId":   m.ID,
		"kind":      m.Kind,
		"title":     m.Name,
		"projectId": projectID,
	}, nil
}

// chatSessionIDFromAgent 由 agentSessionId（ctx）反查 chatSessionId（推 SSE 用）。
func (h *ChatHandler) chatSessionIDFromAgent(ctx context.Context) string {
	sid := agent.SessionIDFromContext(ctx)
	if sid == "" {
		return ""
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.byAgent[sid]
}
