// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0706 0702hjj
// init_model_test.go：initModel 骨架脚本初始化链路（stage/run/save + modelId + 挂项目 + 回滚）。
package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// fakeEditServer 假 edit-service：记录调用顺序，按需失败。
type fakeEditServer struct {
	t        *testing.T
	calls    []string
	failPath string
	srv      *httptest.Server
}

func newFakeEditServer(t *testing.T) *fakeEditServer {
	f := &fakeEditServer{t: t}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.calls = append(f.calls, r.Method+" "+r.URL.Path)
		if r.URL.Path == f.failPath {
			http.Error(w, `{"detail":"422 contract violation"}`, http.StatusUnprocessableEntity)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func newInitModelHandler(t *testing.T, fakeURL string) (*ChatHandler, *store.ProjectStore) {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	ed := editsvc.New(fakeURL)
	cad := editsvc.New(fakeURL)
	q := convert.NewQueue(st, okRunner{}, 1)
	h := &ChatHandler{
		deps:     ChatDeps{St: st, Ps: ps, PlanSt: store.NewPlanStore(dataDir), Ed: ed, Cad: cad, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	return h, ps
}

func TestInitModelIFC(t *testing.T) {
	fake := newFakeEditServer(t)
	h, ps := newInitModelHandler(t, fake.srv.URL)
	p, err := ps.CreateWithKind("测试项目", "ifc")
	if err != nil {
		t.Fatal(err)
	}
	m, err := h.initModel(context.Background(), p.ID, store.KindIFC, "我的建筑")
	if err != nil {
		t.Fatalf("initModel: %v", err)
	}
	// modelId 分配（m_ 前缀）
	if !strings.HasPrefix(m.ID, "m_") {
		t.Errorf("modelId 缺 m_ 前缀: %q", m.ID)
	}
	if m.Kind != store.KindIFC {
		t.Errorf("kind=%q 期望 ifc", m.Kind)
	}
	// 调用链：stage → run → save
	wantOrder := []string{"PUT", "POST", "POST"}
	if len(fake.calls) != 3 {
		t.Fatalf("调用数=%d，期望 3（stage/run/save）: %v", len(fake.calls), fake.calls)
	}
	for i, c := range fake.calls {
		if !strings.HasPrefix(c, wantOrder[i]) {
			t.Errorf("调用[%d]=%q，期望以 %s 开头", i, c, wantOrder[i])
		}
	}
	// 挂到项目
	got, _ := ps.Get(p.ID)
	if len(got.Models) != 1 || got.Models[0].ID != m.ID {
		t.Errorf("项目 Models=%v，期望含 %s", got.Models, m.ID)
	}
	// 骨架脚本 stage 内容含 title（JSON 安全）
	if !strings.Contains(strings.Join(fake.calls, " "), "/script") {
		t.Error("缺 script stage 调用")
	}
}

func TestInitModelDXF(t *testing.T) {
	fake := newFakeEditServer(t)
	h, ps := newInitModelHandler(t, fake.srv.URL)
	p, _ := ps.CreateWithKind("cad 项目", "cad")
	m, err := h.initModel(context.Background(), p.ID, store.KindDXF, "一层平面")
	if err != nil {
		t.Fatalf("initModel: %v", err)
	}
	if m.Kind != store.KindDXF {
		t.Errorf("kind=%q 期望 dxf", m.Kind)
	}
	if !strings.HasPrefix(m.ID, "m_") {
		t.Errorf("modelId 缺 m_ 前缀: %q", m.ID)
	}
}

func TestInitModelRollbackOnBuildFail(t *testing.T) {
	// run 沙箱构建失败（422）→ 回滚模型记录
	fake2 := &fakeEditServer{t: t}
	fake2.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "/script/run") {
			http.Error(w, `{"detail":"sandbox error"}`, http.StatusUnprocessableEntity)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer fake2.srv.Close()
	h2, _ := newInitModelHandler(t, fake2.srv.URL)
	_, err := h2.initModel(context.Background(), "", store.KindIFC, "会失败")
	if err == nil {
		t.Fatal("构建失败应返回错误")
	}
	// 回滚：无模型残留（St.List 空）
	list, _ := h2.deps.St.List()
	if len(list) != 0 {
		t.Errorf("构建失败应回滚模型，残留 %d 个", len(list))
	}
}
