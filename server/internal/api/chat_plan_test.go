// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_plan_test.go：B1 方案级存储端点契约（GET/PUT plan.json/bim_supplement.json + plan_history）。
package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"ifcviewer/server/internal/store"
)

// planHandlerWithProject 构造带 ProjectSt + PlanSt 的 ChatHandler，并预建一个项目。
func planHandlerWithProject(t *testing.T) (*ChatHandler, *store.Project) {
	t.Helper()
	dataDir := t.TempDir()
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, store.NewStore(dataDir), ps)
	h.deps.Ps = ps
	h.deps.PlanSt = store.NewPlanStore(dataDir)
	p, err := ps.Create("P")
	if err != nil {
		t.Fatal(err)
	}
	return h, p
}

// TestPlanPutGetEndpoint PUT/GET plan.json 往返（envelope + 版本）。
func TestPlanPutGetEndpoint(t *testing.T) {
	h, p := planHandlerWithProject(t)

	// PUT plan.json
	put := httptest.NewRequest(http.MethodPut, "/api/v1/projects/"+p.ID+"/plan.json",
		strings.NewReader(`{"content":{"version":1,"project":"`+p.ID+`"}}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, put)
	if rec.Code != http.StatusOK {
		t.Fatalf("put status = %d body=%s", rec.Code, rec.Body.String())
	}
	var e struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &e)
	var r struct {
		Version string `json:"version"`
	}
	_ = json.Unmarshal(e.Data, &r)
	if r.Version != "v1" {
		t.Fatalf("put version = %q, want v1", r.Version)
	}

	// GET plan.json
	get := httptest.NewRequest(http.MethodGet, "/api/v1/projects/"+p.ID+"/plan.json", nil)
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, get)
	if rec.Code != http.StatusOK {
		t.Fatalf("get status = %d", rec.Code)
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &e)
	var g struct {
		Version string          `json:"version"`
		Content json.RawMessage `json:"content"`
	}
	_ = json.Unmarshal(e.Data, &g)
	if g.Version != "v1" || !strings.Contains(string(g.Content), `"project":"`+p.ID+`"`) {
		t.Fatalf("get = %+v", g)
	}
}

// TestPlanEndpointValidation 项目不存在 / 非法 body → 4xx（verify 层）。
func TestPlanEndpointValidation(t *testing.T) {
	h, p := planHandlerWithProject(t)

	// 项目不存在
	req := httptest.NewRequest(http.MethodGet, "/api/v1/projects/p_0000000000000000/plan.json", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest && rec.Code != http.StatusNotFound {
		t.Fatalf("missing project status = %d", rec.Code)
	}

	// 非法 JSON body
	put := httptest.NewRequest(http.MethodPut, "/api/v1/projects/"+p.ID+"/plan.json",
		strings.NewReader(`{"content":"not-json"}`))
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, put)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("bad json status = %d body=%s", rec.Code, rec.Body.String())
	}
}

// TestPlanHistoryEndpoint plan_history 列表（版本化可见）。
func TestPlanHistoryEndpoint(t *testing.T) {
	h, p := planHandlerWithProject(t)
	planContent := `{"content":{"version":1,"project":"` + p.ID + `"}}`
	for i := 0; i < 2; i++ {
		put := httptest.NewRequest(http.MethodPut, "/api/v1/projects/"+p.ID+"/plan.json", strings.NewReader(planContent))
		rec := httptest.NewRecorder()
		h.mux.ServeHTTP(rec, put)
		if rec.Code != http.StatusOK {
			t.Fatalf("put#%d status = %d", i, rec.Code)
		}
	}
	req := httptest.NewRequest(http.MethodGet, "/api/v1/projects/"+p.ID+"/plan_history", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("history status = %d", rec.Code)
	}
	var e struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &e)
	var r struct {
		Name    string   `json:"name"`
		History []string `json:"history"`
	}
	_ = json.Unmarshal(e.Data, &r)
	if r.Name != "plan.json" || len(r.History) != 1 {
		t.Fatalf("history = %+v, want [v1]", r)
	}
}
