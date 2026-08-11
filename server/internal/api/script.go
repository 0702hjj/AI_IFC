// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
)

// registerScriptRoutes 暴露 script-as-source 编辑/暂存/大版本端点（代理到 edit-service）。
// WPS 式暂存（10 步脚本快照）→ 沙箱执行 → 显式 save 成为大版本（scripts/v{n}.py +
// versions/v{n}.ifc）；不做逐步回溯链。design JSON 端点已随 W-0011 下线。
func (h *handler) registerScriptRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/models/{id}/script", h.scriptGet)
	mux.HandleFunc("PUT /api/v1/models/{id}/script", h.scriptPut)
	mux.HandleFunc("GET /api/v1/models/{id}/script/params", h.scriptParams)
	mux.HandleFunc("POST /api/v1/models/{id}/script/undo", h.scriptPost("undo"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/redo", h.scriptPost("redo"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/discard", h.scriptPost("discard"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/run", h.scriptMutatingPost("run"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/save", h.scriptMutatingPost("save"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/rollback", h.scriptMutatingPost("rollback"))
	mux.HandleFunc("POST /api/v1/models/{id}/script/diff", h.scriptPost("diff"))
	mux.HandleFunc("GET /api/v1/models/{id}/script/staging/diff", h.scriptStagingDiff)
	mux.HandleFunc("GET /api/v1/models/{id}/script/locate", h.scriptLocate)
	mux.HandleFunc("GET /api/v1/models/{id}/scripts", h.scriptList)
}

func (h *handler) scriptGet(w http.ResponseWriter, r *http.Request) {
	h.scriptProxy(w, r, http.MethodGet, "/models/"+r.PathValue("id")+"/script", nil)
}

func (h *handler) scriptPut(w http.ResponseWriter, r *http.Request) {
	body := readBody(w, r)
	if body == nil {
		return
	}
	h.scriptProxy(w, r, http.MethodPut, "/models/"+r.PathValue("id")+"/script", body)
}

func (h *handler) scriptParams(w http.ResponseWriter, r *http.Request) {
	h.scriptProxy(w, r, http.MethodGet, "/models/"+r.PathValue("id")+"/script/params", nil)
}

func (h *handler) scriptPost(action string) func(http.ResponseWriter, *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		body := readBody(w, r)
		if body == nil {
			return
		}
		h.scriptProxy(w, r, http.MethodPost, "/models/"+r.PathValue("id")+"/script/"+action, body)
	}
}

// scriptMutatingPost 用于会重写 uploads/{id}.ifc 的动作（run/save/rollback，
// 见 edit-service routes_scripts.py _run_into_uploads）：成功后排 XKT 重转，
// 否则前端 3D 不刷新（M5 集成缺口）。沙箱执行最长 60s（RUN_TIMEOUT_S），
// 必须走 slow client（M5 终审 C2）。
func (h *handler) scriptMutatingPost(action string) func(http.ResponseWriter, *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		body := readBody(w, r)
		if body == nil {
			return
		}
		modelID := r.PathValue("id")
		if !h.scriptProxyDo(w, r, http.MethodPost, "/models/"+modelID+"/script/"+action, body, h.ed.DoSlow) {
			return
		}
		if err := h.st.SetStatus(modelID, "converting", ""); err != nil {
			log.Printf("script %s %s: set converting: %v", action, modelID, err)
		}
		if !h.q.Enqueue(modelID) {
			log.Printf("script %s %s: conversion already pending", action, modelID)
		}
	}
}

func (h *handler) scriptList(w http.ResponseWriter, r *http.Request) {	h.scriptProxy(w, r, http.MethodGet, "/models/"+r.PathValue("id")+"/scripts", nil)
}

// scriptStagingDiff 小版本 diff（暂存链步间）：query（from/to）原样透传。
func (h *handler) scriptStagingDiff(w http.ResponseWriter, r *http.Request) {
	path := "/models/" + r.PathValue("id") + "/script/staging/diff"
	if r.URL.RawQuery != "" {
		path += "?" + r.URL.RawQuery
	}
	h.scriptProxy(w, r, http.MethodGet, path, nil)
}

// scriptLocate guid → 脚本调用点（designKey/line/col/snippet/origin）：query（guid）原样透传。
// miss 返回 200 {found:false}（契约违规属 bug，不 5xx）。
func (h *handler) scriptLocate(w http.ResponseWriter, r *http.Request) {
	path := "/models/" + r.PathValue("id") + "/script/locate"
	if r.URL.RawQuery != "" {
		path += "?" + r.URL.RawQuery
	}
	h.scriptProxy(w, r, http.MethodGet, path, nil)
}

// scriptProxy 透传 edit-service 的 script 端点（包 envelope + 错误映射，P0-1 教训）。
// 返回 edit-service 调用是否成功（供成功后编排重转）。只读/轻量端点走 fast client。
func (h *handler) scriptProxy(w http.ResponseWriter, r *http.Request, method, path string, body []byte) bool {
	return h.scriptProxyDo(w, r, method, path, body, h.ed.Do)
}

// scriptProxyDo 用指定 client 方法转发（Do=fast 只读；DoSlow=slow 沙箱执行）。
func (h *handler) scriptProxyDo(w http.ResponseWriter, r *http.Request, method, path string, body []byte,
	do func(context.Context, string, string, []byte) (json.RawMessage, error)) bool {
	raw, err := do(r.Context(), method, path, body)
	if err != nil {
		log.Printf("script %s %s: %v", method, path, err)
		writeEditErr(w, err)
		return false
	}
	writeJSON(w, raw)
	return true
}
