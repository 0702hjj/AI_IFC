// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_plan.go：B1 方案级存储端点（交付对齐）——plan.json / bim_supplement.json
// 读写 + 方案级版本化（plan_history 列表）。
//
// 路由：/api/v1/projects/{projectID}/{name}（name 白名单 plan.json|bim_supplement.json）
//       /api/v1/projects/{projectID}/plan_history
// 归属：chat mux（方案/项目是 chat 模块引入的资源，与 create_project 同族）。
package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"strconv"

	"ifcviewer/server/internal/store"
)

// verifyPlanProject 校验 projectID 格式 + 项目存在（verify 层单点，404/400 翻译）。
func (h *ChatHandler) verifyPlanProject(w http.ResponseWriter, projectID string) bool {
	if h.deps.Ps == nil || h.deps.PlanSt == nil {
		writeErr(w, http.StatusBadGateway, codeBadGateway, "plan store 未配置")
		return false
	}
	if _, err := h.deps.Ps.Get(projectID); err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, http.StatusNotFound, codeNotFound, "project not found: "+projectID)
		} else {
			writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		}
		return false
	}
	return true
}

// getPlanFile 读方案产物（GET /projects/{projectID}/{name}）。
func (h *ChatHandler) getPlanFile(w http.ResponseWriter, r *http.Request) {
	projectID := r.PathValue("projectID")
	if !h.verifyPlanProject(w, projectID) {
		return
	}
	name := r.PathValue("name")
	content, ok := verifyPlanFile(w, h.deps.PlanSt, projectID, name)
	if !ok {
		return
	}
	// 当前版本 = 历史版本数 + 1（首次落盘 = v1）。
	version := "v1"
	if hist, herr := h.deps.PlanSt.ListHistory(projectID, name); herr == nil {
		version = "v" + strconv.Itoa(len(hist)+1)
	}
	writeJSON(w, map[string]any{
		"projectId": projectID,
		"name":      name,
		"version":   version,
		"content":   json.RawMessage(content),
	})
}

// verifyPlanFile 读方案产物（verify 层单点）：产物未落盘 → 404（业务规则住 verify）。
func verifyPlanFile(w http.ResponseWriter, ps *store.PlanStore, projectID, name string) ([]byte, bool) {
	content, err := ps.Get(projectID, name)
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, http.StatusNotFound, codeNotFound, "plan 产物未落盘: "+name)
		} else {
			writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		}
		return nil, false
	}
	return content, true
}

// putPlanFile 写方案产物（PUT /projects/{projectID}/{name}）：body {content: <json 对象>}。
// 轻校验（合法 JSON + project 字段 = projectID）后落盘 + 版本化（PlanStore.Put）。
func (h *ChatHandler) putPlanFile(w http.ResponseWriter, r *http.Request) {
	projectID := r.PathValue("projectID")
	if !h.verifyPlanProject(w, projectID) {
		return
	}
	name := r.PathValue("name")
	var body struct {
		Content json.RawMessage `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	if len(body.Content) == 0 {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "content 缺失")
		return
	}
	if err := verifyPlanContent(body.Content, projectID); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	version, err := h.deps.PlanSt.Put(projectID, name, body.Content)
	if err != nil {
		if errors.Is(err, store.ErrInvalidKind) {
			writeErr(w, http.StatusBadRequest, codeInvalidType, "不支持的方案产物名: "+name)
		} else if errors.Is(err, store.ErrInvalidJSON) {
			writeErr(w, http.StatusBadRequest, codeInvalidType, "content 不是合法 JSON")
		} else {
			writeErr(w, http.StatusInternalServerError, codeInternal, err.Error())
		}
		return
	}
	writeJSON(w, map[string]any{"projectId": projectID, "name": name, "version": version})
}

// verifyPlanContent 轻校验方案产物：合法 JSON 对象 + project 字段 = projectID
// （P-3 共享 ID 对齐）。详细 schema 校验由 aiplan land / 调用方承担（B2）。
func verifyPlanContent(raw json.RawMessage, projectID string) error {
	if !json.Valid(raw) {
		return errors.New("content 不是合法 JSON")
	}
	var obj map[string]any
	if err := json.Unmarshal(raw, &obj); err != nil || obj == nil {
		return errors.New("content 必须是 JSON 对象")
	}
	if proj, _ := obj["project"].(string); proj != "" && proj != projectID {
		return errors.New("content.project 与 projectId 不一致（共享 ID 对齐）")
	}
	return nil
}

// listPlanHistory 列方案产物历史版本（GET /projects/{projectID}/plan_history?name=plan.json）。
func (h *ChatHandler) listPlanHistory(w http.ResponseWriter, r *http.Request) {
	projectID := r.PathValue("projectID")
	if !h.verifyPlanProject(w, projectID) {
		return
	}
	name := r.URL.Query().Get("name")
	if name == "" {
		name = "plan.json"
	}
	history, err := h.deps.PlanSt.ListHistory(projectID, name)
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	writeJSON(w, map[string]any{"projectId": projectID, "name": name, "history": history})
}

// diffPlanHistory 方案级 JSON diff（GET /projects/{projectID}/plan_history/{base}/{target}/diff）。
// base/target 为历史版本（v{n}）；读两版内容做字段级 diff（B3：方案演化可追溯）。
func (h *ChatHandler) diffPlanHistory(w http.ResponseWriter, r *http.Request) {
	projectID := r.PathValue("projectID")
	if !h.verifyPlanProject(w, projectID) {
		return
	}
	name := r.URL.Query().Get("name")
	if name == "" {
		name = "plan.json"
	}
	base := r.PathValue("base")
	target := r.PathValue("target")
	baseContent, ok := verifyPlanHistoryVersion(w, h.deps.PlanSt, projectID, name, base)
	if !ok {
		return
	}
	targetContent, ok := verifyPlanHistoryVersion(w, h.deps.PlanSt, projectID, name, target)
	if !ok {
		return
	}
	changes, err := store.JSONDiff(baseContent, targetContent)
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		return
	}
	writeJSON(w, map[string]any{
		"projectId": projectID, "name": name, "base": base, "target": target,
		"changes": changes,
	})
}

// verifyPlanHistoryVersion 读 diff 一侧内容（verify 层单点）："current" 读当前态
// （常见用法：v1 → current 看最近演化），否则读历史版本；不存在 → 404。
func verifyPlanHistoryVersion(w http.ResponseWriter, ps *store.PlanStore, projectID, name, version string) ([]byte, bool) {
	var content []byte
	var err error
	if version == "current" {
		content, err = ps.Get(projectID, name)
	} else {
		content, err = ps.LoadHistory(projectID, name, version)
	}
	if err != nil {
		if errors.Is(err, store.ErrNotFound) {
			writeErr(w, http.StatusNotFound, codeNotFound, "plan 版本不存在: "+version)
		} else {
			writeErr(w, http.StatusBadRequest, codeInvalidType, err.Error())
		}
		return nil, false
	}
	return content, true
}
