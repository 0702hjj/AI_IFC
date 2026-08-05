// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"log"
	"net/http"
)

// registerDesignRoutes 暴露 design-JSON 编辑/暂存/大版本端点（代理到 edit-service）。
// WPS 式暂存（10 步）→ 显式 save 成为大版本；不做逐步回溯链。
func (h *handler) registerDesignRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/v1/models/{id}/design", h.designGet)
	mux.HandleFunc("PUT /api/v1/models/{id}/design", h.designPut)
	mux.HandleFunc("POST /api/v1/models/{id}/design/undo", h.designPost("undo"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/redo", h.designPost("redo"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/discard", h.designPost("discard"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/save", h.designPost("save"))
	mux.HandleFunc("GET /api/v1/models/{id}/designs", h.designList)
	mux.HandleFunc("POST /api/v1/models/{id}/design/rollback", h.designPost("rollback"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/diff", h.designPost("diff"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/diff-ifc", h.designPost("diff-ifc"))
}

func (h *handler) designGet(w http.ResponseWriter, r *http.Request) {
	h.designProxy(w, r, http.MethodGet, "/models/"+r.PathValue("id")+"/design", nil)
}

func (h *handler) designPut(w http.ResponseWriter, r *http.Request) {
	body := readBody(w, r)
	if body == nil {
		return
	}
	h.designProxy(w, r, http.MethodPut, "/models/"+r.PathValue("id")+"/design", body)
}

func (h *handler) designPost(action string) func(http.ResponseWriter, *http.Request) {
	return func(w http.ResponseWriter, r *http.Request) {
		body := readBody(w, r)
		if body == nil {
			return
		}
		h.designProxy(w, r, http.MethodPost, "/models/"+r.PathValue("id")+"/design/"+action, body)
	}
}

func (h *handler) designList(w http.ResponseWriter, r *http.Request) {
	h.designProxy(w, r, http.MethodGet, "/models/"+r.PathValue("id")+"/designs", nil)
}

// designProxy 透传 edit-service 的 design 端点（包络 + 错误映射）。
func (h *handler) designProxy(w http.ResponseWriter, r *http.Request, method, path string, body []byte) {
	raw, err := h.ed.Do(r.Context(), method, path, body)
	if err != nil {
		log.Printf("design %s %s: %v", method, path, err)
		writeEditErr(w, err)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(raw)
}
