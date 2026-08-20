// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_project_test.go：A1（create_project 项目级）+ A2（会话绑定项目）契约测试。
package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
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

// TestCreateProjectBlank 空白化：只建项目（projectId + 空 models），不产任何模型。
func TestCreateProjectBlank(t *testing.T) {
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, st, ps)

	r := doCreateProject(t, h, `{"title":"A 项目","kind":"cad"}`)
	if r.ProjectID == "" {
		t.Fatalf("missing projectId: %+v", r)
	}
	if r.ID != "" {
		t.Fatalf("空白项目不应产模型（id = %q）", r.ID)
	}
	// 项目落盘 + 无模型
	p, err := ps.Get(r.ProjectID)
	if err != nil {
		t.Fatalf("project get: %v", err)
	}
	if len(p.Models) != 0 {
		t.Fatalf("空白项目 models = %+v, want 空", p.Models)
	}
	// 不产模型文件
	if ms, _ := st.List(); len(ms) != 0 {
		t.Fatalf("空白项目不应注册模型: %+v", ms)
	}
}

// TestCreateProjectKind 项目类型保留（kind = 项目类型，不产模型）。
func TestCreateProjectKind(t *testing.T) {
	dataDir := t.TempDir()
	ps := store.NewProjectStore(dataDir)
	h := newProjectChatHandler(t, store.NewStore(dataDir), ps)

	r := doCreateProject(t, h, `{"title":"D 项目","kind":"cad"}`)
	if r.Kind != "cad" {
		t.Fatalf("kind = %q, want cad（项目类型）", r.Kind)
	}
	p, err := ps.Get(r.ProjectID)
	if err != nil || p.Kind != "cad" {
		t.Fatalf("project kind = %q, want cad", p.Kind)
	}
	if len(p.Models) != 0 {
		t.Fatalf("kind 项目也不应产模型: %+v", p.Models)
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

// TestCreateProjectKindRequired 强制预选：kind 缺失/非法 → 400（verify 层）。
func TestCreateProjectKindRequired(t *testing.T) {
	h := newProjectChatHandler(t, store.NewStore(t.TempDir()), store.NewProjectStore(t.TempDir()))
	for _, body := range []string{`{"title":"x"}`, `{"title":"x","kind":""}`, `{"title":"x","kind":"bad"}`} {
		req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/projects", strings.NewReader(body))
		rec := httptest.NewRecorder()
		h.mux.ServeHTTP(rec, req)
		if rec.Code != http.StatusBadRequest {
			t.Fatalf("body=%s status=%d, want 400", body, rec.Code)
		}
	}
}
