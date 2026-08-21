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
	"encoding/json"
	"fmt"
	"net/http"
	"strings"

	"ifcviewer/server/internal/store"
)

// initModel 初始化一个骨架模型（script-as-source：骨架脚本构建出最小模型 v1）。
//
// 返回：*store.Model（含分配的 modelId）。失败回滚模型记录（骨架构建失败不留空模型）。
func (h *ChatHandler) initModel(ctx context.Context, projectID, kind, title string) (*store.Model, error) {
	skelScript := skeletonIFCScript
	storeKind := store.KindIFC
	if kind == store.KindDXF {
		skelScript = skeletonDXFScript
		storeKind = store.KindDXF
	} else if kind != store.KindIFC {
		return nil, fmt.Errorf("initModel kind 仅支持 ifc/dxf，got %q", kind)
	}
	if h.deps.St == nil {
		return nil, fmt.Errorf("model store 未配置")
	}
	// 骨架脚本填 title（JSON 安全字符串，防引号破坏 Python dict 字面量）
	titleJSON, _ := json.Marshal(title)
	script := strings.ReplaceAll(skelScript, `{"title": "{title}"}`, `{"title": `+string(titleJSON)+`}`)

	// 1. 创建模型记录（分配 modelId；骨架构建前空文件占位，kind 决定初始 status）
	m, err := h.deps.St.CreateWithKind(title, 0, strings.NewReader(""), storeKind)
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

	// 5. 挂到项目（projectID 非空时；D13 后 agent 经 init_model 挂 Project.Models）
	if projectID != "" && h.deps.Ps != nil {
		if err := h.deps.Ps.AddModel(projectID, m.ID, storeKind, title, "ready"); err != nil {
			// 挂项目失败不回滚模型（模型已可用，仅聚合缺失——幂等重挂由后续 AddModel 覆盖）。
			return m, nil
		}
	}

	// 6. ifc kind 排队 XKT 重转（dxf 无 XKT 产物，render.json 直挂）。
	if storeKind == store.KindIFC && h.deps.Q != nil {
		h.deps.Q.EnqueueIfStale(m.ID)
	}
	return m, nil
}

// initModelForAgentTool 是 agent.ToolDeps.InitModel 的适配：返回可 JSON 化的模型信息。
func (h *ChatHandler) initModelForAgentTool(ctx context.Context, projectID, kind, title string) (any, error) {
	m, err := h.initModel(ctx, projectID, kind, title)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"modelId":   m.ID,
		"kind":      m.Kind,
		"title":     m.Name,
		"projectId": projectID,
	}, nil
}
