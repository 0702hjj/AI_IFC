// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"

	"ifcviewer/server/internal/editsvc"
)

const (
	codeConflict       = 40900
	codeBadGateway     = 50200
	codeGatewayTimeout = 50400
)

func (h *handler) registerEditRoutes(mux *http.ServeMux) {
	// L1 直改代理（PUT/DELETE entities、editable-schema、commit、overrides/migrate）
	// 已随 script-as-source 退役：edit-service 侧 410，Go 侧路由不再注册（404）。
	// 保留只读/pending 存量/diff 代理。
	mux.HandleFunc("GET /api/v1/models/{id}/edit/pending", h.editGetPending)
	mux.HandleFunc("DELETE /api/v1/models/{id}/edit/pending", h.editDeletePending)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/history", h.editHistory)
	mux.HandleFunc("GET /api/v1/models/{id}/edit/versions", h.editVersions)
	mux.HandleFunc("POST /api/v1/models/{id}/edit/diff", h.editDiff)
}

// writeEditErr 透传 Python 状态码语义：404→404、409→409、422→400、504→504（diff
// 超时，edit-service DIFF_TIMEOUT_S 默认 60s），其余（含不可达）→502。
func writeEditErr(w http.ResponseWriter, err error) {
	var ee *editsvc.Error
	if errors.As(err, &ee) {
		switch ee.Status {
		case http.StatusNotFound:
			writeErr(w, http.StatusNotFound, codeNotFound, ee.Detail)
		case http.StatusConflict:
			writeErr(w, http.StatusConflict, codeConflict, ee.Detail)
		case http.StatusUnprocessableEntity:
			writeErr(w, http.StatusBadRequest, codeInvalidType, ee.Detail)
		case http.StatusGatewayTimeout:
			writeErr(w, http.StatusGatewayTimeout, codeGatewayTimeout, ee.Detail)
		default:
			writeErr(w, http.StatusBadGateway, codeBadGateway, "edit service error: "+ee.Detail)
		}
		return
	}
	writeErr(w, http.StatusBadGateway, codeBadGateway, err.Error())
}

func readBody(w http.ResponseWriter, r *http.Request) []byte {
	r.Body = http.MaxBytesReader(w, r.Body, 1<<20)
	data, err := io.ReadAll(r.Body)
	if err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid request body")
		return nil
	}
	return data
}

func (h *handler) editGetPending(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.GetPending(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editDeletePending(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.DeletePending(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editHistory(w http.ResponseWriter, r *http.Request) {
	m := h.modelOrErr(w, r.PathValue("id"))
	if m == nil {
		return
	}
	data, err := h.ed.GetHistory(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}

func (h *handler) editVersions(w http.ResponseWriter, r *http.Request) {
	m, cl := h.editClientFor(w, r.PathValue("id"))
	if cl == nil {
		return
	}
	versions, err := cl.GetVersions(r.Context(), m.ID)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, versions)
}

func (h *handler) editDiff(w http.ResponseWriter, r *http.Request) {
	m, cl := h.editClientFor(w, r.PathValue("id"))
	if cl == nil {
		return
	}
	body := readBody(w, r)
	if body == nil {
		return
	}
	data, err := cl.PostDiff(r.Context(), m.ID, body)
	if err != nil {
		writeEditErr(w, err)
		return
	}
	writeJSON(w, json.RawMessage(data))
}
