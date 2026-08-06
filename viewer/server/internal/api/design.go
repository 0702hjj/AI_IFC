// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"log"
	"net/http"
)

// registerDesignDiffRoutes 仅保留 design diff 代理（W-0012 统一切换/下线）。
// design JSON 编辑/暂存/大版本端点已随 W-0011 替换为 script 端点（见 script.go）。
func (h *handler) registerDesignDiffRoutes(mux *http.ServeMux) {
	mux.HandleFunc("POST /api/v1/models/{id}/design/diff", h.designPost("diff"))
	mux.HandleFunc("POST /api/v1/models/{id}/design/diff-ifc", h.designPost("diff-ifc"))
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

// designProxy 透传 edit-service 的 design diff 端点（包络 + 错误映射）。
func (h *handler) designProxy(w http.ResponseWriter, r *http.Request, method, path string, body []byte) {
	raw, err := h.ed.Do(r.Context(), method, path, body)
	if err != nil {
		log.Printf("design %s %s: %v", method, path, err)
		writeEditErr(w, err)
		return
	}
	writeJSON(w, raw)
}
