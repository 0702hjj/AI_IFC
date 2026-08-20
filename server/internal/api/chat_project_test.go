// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_project_test.go：A1（create_project 项目级）+ A2（会话绑定项目）契约测试。
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

// newProjectChatHandler 构造带 ProjectSt 的 ChatHandler（复用 chat_tools_test 装配模式）。
func newProjectChatHandler(t *testing.T, st *store.Store, ps *store.ProjectStore) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	q := convert.NewQueue(st, okRunner{}, 1)
	h := &ChatHandler{
		deps:     ChatDeps{St: st, Ps: ps, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// projectCreateResp 是 create_project 返回的兼容结构（id=首模型 + projectId 新字段）。
type projectCreateResp struct {
	ID        string `json:"id"`
	ProjectID string `json:"projectId"`
	Kind      string `json:"kind"`
	Status    string `json:"status"`
}

// doCreateProject 调 POST /api/v1/chat/projects 并解 envelope。
func doCreateProject(t *testing.T, h *ChatHandler, body string) projectCreateResp {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/projects", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.createProject(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body=%s", rec.Code, rec.Body.String())
	}
	var e struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil || e.Code != 0 {
		t.Fatalf("envelope: %v code=%d body=%s", err, e.Code, rec.Body.String())
	}
	var r projectCreateResp
	if err := json.Unmarshal(e.Data, &r); err != nil {
		t.Fatal(err)
	}
	return r
}

// TestCreateProjectIFC 默认 kind=ifc：返回兼容结构（id=首模型）+ projectId 新字段。
func TestCreateProjectIFC(t *testing.T) {
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, st, ps)

	r := doCreateProject(t, h, `{"title":"A 项目"}`)
	if r.ID == "" || r.ProjectID == "" {
		t.Fatalf("missing id/projectId: %+v", r)
	}
	if r.ID == r.ProjectID {
		t.Fatalf("model id should differ from project id")
	}
	if r.Kind != "ifc" || r.Status != "converting" {
		t.Fatalf("kind/status = %q/%q, want ifc/converting", r.Kind, r.Status)
	}
	// 项目落盘 + 模型挂入
	p, err := ps.Get(r.ProjectID)
	if err != nil {
		t.Fatalf("project get: %v", err)
	}
	if len(p.Models) != 1 || p.Models[0].ID != r.ID {
		t.Fatalf("project models = %+v, want [%s]", p.Models, r.ID)
	}
}

// TestCreateProjectDXF kind=dxf：模型直接 ready + dxf 文件落盘。
func TestCreateProjectDXF(t *testing.T) {
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, st, ps)

	r := doCreateProject(t, h, `{"title":"D 项目","kind":"dxf"}`)
	if r.Kind != "dxf" || r.Status != "ready" {
		t.Fatalf("kind/status = %q/%q, want dxf/ready", r.Kind, r.Status)
	}
	m, err := st.Get(r.ID)
	if err != nil || m.Kind != store.KindDXF {
		t.Fatalf("model: %v %+v", err, m)
	}
	if _, err := os.Stat(st.DXFPath(m.ID)); err != nil {
		t.Fatalf("dxf file missing: %s", st.DXFPath(m.ID))
	}
	// 项目挂入 dxf 模型
	p, _ := ps.Get(r.ProjectID)
	if len(p.Models) != 1 || p.Models[0].Kind != "dxf" {
		t.Fatalf("project models = %+v", p.Models)
	}
}

// TestCreateSessionWithProjectID A2：会话绑定项目 + 幂等。
func TestCreateSessionWithProjectID(t *testing.T) {
	dataDir := t.TempDir()
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, store.NewStore(dataDir), ps)
	p, err := ps.Create("P")
	if err != nil {
		t.Fatal(err)
	}
	body := fmt.Sprintf(`{"title":"t","projectId":%q}`, p.ID)
	first := doChatCreateJSON(t, h, body)
	if first.ProjectID != p.ID {
		t.Fatalf("session projectId = %q, want %q", first.ProjectID, p.ID)
	}
	second := doChatCreateJSON(t, h, body)
	if second.ID != first.ID {
		t.Fatalf("idempotent: %q != %q", second.ID, first.ID)
	}
}

// TestCreateSessionProjectIdNotFound 绑定不存在的项目 → 400（verify 层）。
func TestCreateSessionProjectIdNotFound(t *testing.T) {
	dataDir := t.TempDir()
	h := newProjectChatHandler(t, store.NewStore(dataDir), store.NewProjectStore(dataDir))
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions", strings.NewReader(`{"title":"t","projectId":"p_0000000000000000"}`))
	rec := httptest.NewRecorder()
	h.createSession(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", rec.Code)
	}
}

// doChatCreateJSON 直接调 createSession 并解 envelope，返回 chatSession。
func doChatCreateJSON(t *testing.T, h *ChatHandler, body string) *chatSession {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.createSession(rec, req)
	var e struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil || e.Code != 0 {
		t.Fatalf("envelope: %v code=%d body=%s", err, e.Code, rec.Body.String())
	}
	var cs chatSession
	if err := json.Unmarshal(e.Data, &cs); err != nil {
		t.Fatal(err)
	}
	return &cs
}
