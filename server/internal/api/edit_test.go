// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/override"
	"ifcviewer/server/internal/store"
)

type pyCall struct {
	Method   string
	Path     string
	RawQuery string
	Body     string
}

type pyResp struct {
	status int
	body   string
}

// fakePy 是脚本化的假 Python 编辑服务：按 method+path 匹配预设响应，并记录所有请求。
type fakePy struct {
	mu     sync.Mutex
	calls  []pyCall
	routes map[string]pyResp
}

func newFakePy(t *testing.T) (*fakePy, string) {
	t.Helper()
	f := &fakePy{routes: map[string]pyResp{}}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		f.mu.Lock()
		f.calls = append(f.calls, pyCall{Method: r.Method, Path: r.URL.Path, RawQuery: r.URL.RawQuery, Body: string(body)})
		resp, ok := f.routes[r.Method+" "+r.URL.Path]
		f.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			w.Write([]byte(`{"detail":"not scripted"}`))
			return
		}
		w.WriteHeader(resp.status)
		w.Write([]byte(resp.body))
	}))
	t.Cleanup(srv.Close)
	return f, srv.URL
}

func (f *fakePy) set(method, path string, status int, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.routes[method+" "+path] = pyResp{status: status, body: body}
}

func (f *fakePy) callCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.calls)
}

func (f *fakePy) lastCall() pyCall {
	f.mu.Lock()
	defer f.mu.Unlock()
	if len(f.calls) == 0 {
		return pyCall{}
	}
	return f.calls[len(f.calls)-1]
}

type spyRunner struct{ runs chan string }

func (s spyRunner) Run(ctx context.Context, in, out string) error {
	s.runs <- in
	return nil
}

type editEnv struct {
	mux     http.Handler
	modelID string
	st      *store.Store
	chg     change.Store
	ovr     *override.FileStore
	ed      *editsvc.Client
	q       *convert.Queue
	runs    chan string
}

func newEditEnv(t *testing.T, pyURL string) *editEnv {
	t.Helper()
	return newEditEnvChg(t, pyURL, nil)
}

// newEditEnvChg 允许注入自定义 change.Store（nil 用默认 FileStore）。
func newEditEnvChg(t *testing.T, pyURL string, chg change.Store) *editEnv {
	t.Helper()
	var ed *editsvc.Client
	if pyURL != "" {
		ed = editsvc.New(pyURL)
	}
	return newEditEnvWithClient(t, ed, chg)
}

// newEditEnvWithClient 允许注入自定义 editsvc.Client（如短超时断言 client 选择）。
func newEditEnvWithClient(t *testing.T, ed *editsvc.Client, chg change.Store) *editEnv {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	runs := make(chan string, 4)
	q := convert.NewQueue(st, spyRunner{runs: runs}, 1)
	q.Start(ctx)
	if chg == nil {
		chg = change.NewFileStore(st.DataDir)
	}
	ovr := override.NewFileStore(st.DataDir)
	mux := NewHandler(st, q, issue.NewFileStore(st.DataDir), chg, ovr, ed, nil, 1<<20)
	m, err := st.Create("ok.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	if err := st.SetStatus(m.ID, "ready", ""); err != nil {
		t.Fatal(err)
	}
	return &editEnv{mux: mux, modelID: m.ID, st: st, chg: chg, ovr: ovr, ed: ed, q: q, runs: runs}
}

// failAppendChangeStore 仅 Append 失败，模拟 change log 磁盘写失败。
type failAppendChangeStore struct{ err error }

func (f failAppendChangeStore) List(modelID string) ([]*change.Entry, error) { return nil, nil }
func (f failAppendChangeStore) Append(modelID string, entries ...*change.Entry) error {
	return f.err
}
func (f failAppendChangeStore) DeleteModel(modelID string) error { return nil }

func doEditReq(t *testing.T, mux http.Handler, method, path, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr io.Reader
	if body != "" {
		rdr = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, path, rdr)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func decodeEnv(t *testing.T, rec *httptest.ResponseRecorder) env {
	t.Helper()
	var e env
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil {
		t.Fatalf("envelope decode: %v body=%s", err, rec.Body)
	}
	return e
}

func waitRun(t *testing.T, runs chan string) string {
	t.Helper()
	select {
	case in := <-runs:
		return in
	case <-time.After(2 * time.Second):
		t.Fatal("conversion was not enqueued")
		return ""
	}
}

// waitReady 等队列 worker 完成 SetStatus，避免与 TempDir 清理竞争。
func waitReady(t *testing.T, st *store.Store, modelID string) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		m, err := st.Get(modelID)
		if err == nil && m.Status == "ready" {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("model did not become ready")
}

func assertNoRun(t *testing.T, runs chan string) {
	t.Helper()
	select {
	case in := <-runs:
		t.Fatalf("unexpected conversion run: %s", in)
	case <-time.After(100 * time.Millisecond):
	}
}

const fakeVersionsBody = `{"versions":[{"version":"v1","createdAt":"t1"},{"version":"v2","createdAt":"t2"}],"current":"v2"}`

const fakeDiffBody = `{"base":"v1","target":"current","added":[],"removed":[],"changed":[
  {"guid":"g1","changes":[{"field":"Name","old":"Wall A","new":"Wall B"}]}
]}`

// TestEditDirectEditRoutesGone 直改代理路由随 script-as-source 退役：不再注册 → 404。
func TestEditDirectEditRoutesGone(t *testing.T) {
	env := newEditEnv(t, "")
	for _, tc := range []struct{ method, path string }{
		{"PUT", "/edit/entities/g1"},
		{"DELETE", "/edit/entities/g1"},
		{"GET", "/edit/entities/g1/editable-schema"},
		{"POST", "/edit/commit"},
	} {
		rec := doEditReq(t, env.mux, tc.method, "/api/v1/models/"+env.modelID+tc.path, "")
		if rec.Code != http.StatusNotFound {
			t.Fatalf("%s %s: status = %d, want 404 (body %s)", tc.method, tc.path, rec.Code, rec.Body)
		}
	}
}

func TestEditProxyStatusMapping(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	path := "/models/" + env.modelID + "/pending"
	cases := []struct {
		pyStatus   int
		wantStatus int
		wantCode   int
	}{
		{404, http.StatusNotFound, codeNotFound},
		{409, http.StatusConflict, codeConflict},
		{422, http.StatusBadRequest, codeInvalidType},
		{500, http.StatusBadGateway, codeBadGateway},
		{504, http.StatusGatewayTimeout, codeGatewayTimeout},
	}
	for _, c := range cases {
		py.set("GET", path, c.pyStatus, `{"detail":"boom"}`)
		rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/edit/pending", "")
		if rec.Code != c.wantStatus {
			t.Fatalf("py %d: go status = %d, want %d (body %s)", c.pyStatus, rec.Code, c.wantStatus, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != c.wantCode {
			t.Fatalf("py %d: envelope code = %d, want %d", c.pyStatus, e.Code, c.wantCode)
		}
		if !strings.Contains(e.Message, "boom") {
			t.Fatalf("py %d: message = %q, want detail propagated", c.pyStatus, e.Message)
		}
	}
}

func TestEditProxyGetEndpoints(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("GET", "/models/"+env.modelID+"/pending", 200, `[{"id":"e_1","guid":"g1"}]`)
	py.set("DELETE", "/models/"+env.modelID+"/pending", 200, `{"discarded":2}`)
	py.set("GET", "/models/"+env.modelID+"/history", 200, `[{"id":"e_0"}]`)
	py.set("GET", "/models/"+env.modelID+"/versions", 200, fakeVersionsBody)

	cases := []struct {
		method string
		goPath string
		want   string
	}{
		{"GET", "/edit/pending", "e_1"},
		{"DELETE", "/edit/pending", `"discarded":2`},
		{"GET", "/edit/history", "e_0"},
		{"GET", "/edit/versions", `"current":"v2"`},
	}
	for _, c := range cases {
		rec := doEditReq(t, env.mux, c.method, "/api/v1/models/"+env.modelID+c.goPath, "")
		if rec.Code != http.StatusOK {
			t.Fatalf("%s %s: status = %d body = %s", c.method, c.goPath, rec.Code, rec.Body)
		}
		e := decodeEnv(t, rec)
		if !strings.Contains(string(e.Data), c.want) {
			t.Fatalf("%s %s: data = %s, want containing %s", c.method, c.goPath, e.Data, c.want)
		}
	}
}

func TestEditDiffPassthrough(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("POST", "/models/"+env.modelID+"/diff", 200, fakeDiffBody)
	body := `{"base":"v1","target":"current"}`
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/diff", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if !strings.Contains(string(e.Data), `"guid":"g1"`) {
		t.Fatalf("data = %s", e.Data)
	}
	if call := py.lastCall(); call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
	}
}

func TestEditServiceUnreachable(t *testing.T) {
	env := newEditEnv(t, "http://127.0.0.1:1") // 连接拒绝
	for _, tc := range []struct{ method, path, body string }{
		{"GET", "/edit/pending", ""},
		{"POST", "/edit/diff", `{"base":"v1","target":"current"}`},
	} {
		rec := doEditReq(t, env.mux, tc.method, "/api/v1/models/"+env.modelID+tc.path, tc.body)
		if rec.Code != http.StatusBadGateway {
			t.Fatalf("%s %s: status = %d, want 502 (body %s)", tc.method, tc.path, rec.Code, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != codeBadGateway || !strings.Contains(e.Message, "edit service") {
			t.Fatalf("%s %s: envelope = %+v", tc.method, tc.path, e)
		}
	}
}

// TestMigrateRouteGone overrides/migrate 依赖已退役的 L1 直改端点（PUT entities +
// commit），随 script-as-source 一并退役：Go 侧路由不再注册 → 404（Mux 未匹配）。
func TestMigrateRouteGone(t *testing.T) {
	env := newEditEnv(t, "")
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404（migrate 已退役，路由应移除；body %s）", rec.Code, rec.Body)
	}
}
