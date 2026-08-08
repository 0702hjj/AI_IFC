// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
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
	mux := NewHandler(st, q, issue.NewFileStore(st.DataDir), chg, ovr, ed, 1<<20)
	m, err := st.Create("ok.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	if err := st.SetStatus(m.ID, "ready", ""); err != nil {
		t.Fatal(err)
	}
	return &editEnv{mux: mux, modelID: m.ID, st: st, chg: chg, ovr: ovr, runs: runs}
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

const fakeCommitBody = `{"committed":2,"entries":[
  {"id":"e_aaa111","guid":"g1","changes":[
    {"field":"Name","oldValue":"Wall A","newValue":"Wall B"},
    {"field":"Description","oldValue":null,"newValue":"d1"}],
   "author":"ai-bot","provenance":{"source":"AI"},"timestamp":"2026-01-01T00:00:00Z","operation":"update"},
  {"id":"e_bbb222","guid":"g2","changes":[
    {"field":"Name","oldValue":"W2","newValue":"W3"}],
   "author":"ai-bot","provenance":{"source":"AI"},"timestamp":"2026-01-01T00:00:00Z","operation":"update"}
]}`

const fakeVersionsBody = `{"versions":[{"version":"v1","createdAt":"t1"},{"version":"v2","createdAt":"t2"}],"current":"v2"}`

const fakeDiffBody = `{"base":"v1","target":"current","added":[],"removed":[],"changed":[
  {"guid":"g1","changes":[{"field":"Name","old":"Wall A","new":"Wall B"}]}
]}`

func scriptCommit(py *fakePy, modelID string) {
	py.set("POST", "/models/"+modelID+"/commit", 200, fakeCommitBody)
	py.set("GET", "/models/"+modelID+"/versions", 200, fakeVersionsBody)
	py.set("POST", "/models/"+modelID+"/diff", 200, fakeDiffBody)
}

func TestEditPutEntityPassthrough(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	entry := `{"id":"e_aaa111","guid":"g1","changes":[{"field":"Name","oldValue":"A","newValue":"B"}],"author":"local-user","provenance":{"source":"UI"},"timestamp":"t"}`
	py.set("PUT", "/models/"+env.modelID+"/entities/g1", 200, entry)

	body := `{"fields":{"Name":"B"},"author":"local-user","provenance":{"source":"UI"}}`
	rec := doEditReq(t, env.mux, "PUT", "/api/v1/models/"+env.modelID+"/edit/entities/g1", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 {
		t.Fatalf("envelope code = %d msg = %s", e.Code, e.Message)
	}
	var got map[string]interface{}
	if err := json.Unmarshal(e.Data, &got); err != nil {
		t.Fatal(err)
	}
	if got["id"] != "e_aaa111" || got["guid"] != "g1" {
		t.Fatalf("data = %s", e.Data)
	}
	call := py.lastCall()
	if call.Method != "PUT" || call.Path != "/models/"+env.modelID+"/entities/g1" {
		t.Fatalf("call = %+v", call)
	}
	if call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
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

func TestEditPutEntityBadProvenance(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	rec := doEditReq(t, env.mux, "PUT", "/api/v1/models/"+env.modelID+"/edit/entities/g1",
		`{"fields":{"Name":"B"},"provenance":{"source":"robot"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if e := decodeEnv(t, rec); e.Code != codeInvalidType {
		t.Fatalf("code = %d, want %d", e.Code, codeInvalidType)
	}
	if py.callCount() != 0 {
		t.Fatalf("python received %d calls, want 0", py.callCount())
	}
}

func TestEditCommitOrchestration(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	scriptCommit(py, env.modelID)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/commit",
		`{"author":"ai-bot","provenance":{"source":"AI"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Committed    int             `json:"committed"`
		Entries      []editsvc.Entry `json:"entries"`
		Reconverting bool            `json:"reconverting"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if data.Committed != 2 || len(data.Entries) != 2 || !data.Reconverting {
		t.Fatalf("data = %s", e.Data)
	}

	// change log 展开：3 条 field change，Operation=update
	entries, err := env.chg.List(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 3 {
		t.Fatalf("change entries = %+v", entries)
	}
	byKey := map[string]*change.Entry{}
	for _, en := range entries {
		byKey[en.EntityID+"/"+en.Field] = en
		if en.Operation != "update" {
			t.Fatalf("operation = %q, want update", en.Operation)
		}
		if en.Author != "ai-bot" || en.Provenance.Source != "AI" {
			t.Fatalf("entry = %+v", en)
		}
		if len(en.Diff) == 0 {
			t.Fatalf("entry %s/%s: Diff empty", en.EntityID, en.Field)
		}
	}
	g1name := byKey["g1/Name"]
	if g1name == nil || g1name.OldValue != "Wall A" || g1name.NewValue != "Wall B" {
		t.Fatalf("g1/Name entry = %+v", g1name)
	}
	if g1name.EntityName != "" {
		t.Fatalf("EntityName = %q, want empty", g1name.EntityName)
	}
	g1desc := byKey["g1/Description"]
	if g1desc == nil || g1desc.OldValue != "" || g1desc.NewValue != "d1" {
		t.Fatalf("g1/Description entry = %+v", g1desc)
	}
	// diff 补充：g1 的 Diff 被 diff.changed 替换（field/old/new 形状）
	if !strings.Contains(string(g1name.Diff), `"old": "Wall A"`) {
		t.Fatalf("g1 Diff not replaced by diff result: %s", g1name.Diff)
	}
	// g2 不在 diff.changed 中，保留 commit changes 形状（field/oldValue/newValue）
	g2name := byKey["g2/Name"]
	if g2name == nil || !strings.Contains(string(g2name.Diff), `"oldValue": "W2"`) {
		t.Fatalf("g2 Diff = %s", g2name.Diff)
	}

	// 重转被触发
	if in := waitRun(t, env.runs); !strings.Contains(in, env.modelID) {
		t.Fatalf("runner input = %q, want model %s", in, env.modelID)
	}
	waitReady(t, env.st, env.modelID)
}

func TestEditCommitDiffFailureNonBlocking(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	scriptCommit(py, env.modelID)
	py.set("POST", "/models/"+env.modelID+"/diff", 500, `{"detail":"diff exploded"}`)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/commit", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	entries, err := env.chg.List(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 3 {
		t.Fatalf("change entries = %d, want 3", len(entries))
	}
	for _, en := range entries {
		if !strings.Contains(string(en.Diff), `"oldValue"`) {
			t.Fatalf("Diff should keep commit-changes shape on diff failure: %s", en.Diff)
		}
	}
	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestEditCommitChangeLogFailureWarns(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnvChg(t, pyURL, failAppendChangeStore{err: errors.New("change log disk full")})
	scriptCommit(py, env.modelID)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/commit",
		`{"author":"ai-bot","provenance":{"source":"AI"}}`)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Committed    int    `json:"committed"`
		Reconverting bool   `json:"reconverting"`
		Warning      string `json:"warning"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if data.Committed != 2 || !data.Reconverting {
		t.Fatalf("data = %s", e.Data)
	}
	if !strings.Contains(data.Warning, "change log") {
		t.Fatalf("warning = %q, want change log failure surfaced", data.Warning)
	}
	// change log 写失败仍排重转
	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestEditCommitNoPendingConflict(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("POST", "/models/"+env.modelID+"/commit", 409, `{"detail":"no pending changes"}`)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/commit", "")
	if rec.Code != http.StatusConflict {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if e := decodeEnv(t, rec); e.Code != codeConflict {
		t.Fatalf("code = %d, want %d", e.Code, codeConflict)
	}
	entries, _ := env.chg.List(env.modelID)
	if len(entries) != 0 {
		t.Fatalf("entries = %+v, want none", entries)
	}
	assertNoRun(t, env.runs)
}

func TestEditCommitBadProvenance(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/edit/commit",
		`{"provenance":{"source":"robot"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if py.callCount() != 0 {
		t.Fatalf("python received %d calls, want 0", py.callCount())
	}
}

func TestEditServiceUnreachable(t *testing.T) {
	env := newEditEnv(t, "http://127.0.0.1:1") // 连接拒绝
	for _, tc := range []struct{ method, path, body string }{
		{"GET", "/edit/pending", ""},
		{"PUT", "/edit/entities/g1", `{"fields":{"Name":"x"}}`},
		{"GET", "/edit/entities/g1/editable-schema", ""},
		{"DELETE", "/edit/entities/g1", ""},
		{"POST", "/edit/commit", ""},
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

const testMetadata = `{"projectId":"p","metaObjects":[
  {"id":"g1","type":"IfcWall","name":"Wall","parent":null,"propertySetIds":["ps1"]},
  {"id":"g2","type":"IfcWall","name":"Wall2","parent":null,"propertySetIds":[]}],
 "propertySets":[
  {"id":"ps1","name":"Pset_WallCommon","type":"Pset","properties":[{"name":"FireRating","value":"","type":"1"}]}]}`

func writeMetadata(t *testing.T, st *store.Store, modelID, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(st.ModelDir(modelID), "metadata.json"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestMigrateSuccess(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	writeMetadata(t, env.st, env.modelID, testMetadata)
	if _, err := env.ovr.Set(env.modelID, "g1", map[string]string{"Name": "NewName", "FireRating": "F90"}); err != nil {
		t.Fatal(err)
	}
	py.set("PUT", "/models/"+env.modelID+"/entities/g1", 200,
		`{"id":"e_1","guid":"g1","changes":[],"author":"local-user","provenance":{"source":"UI"},"timestamp":"t"}`)
	py.set("POST", "/models/"+env.modelID+"/commit", 200, `{"committed":1,"entries":[
	  {"id":"e_1","guid":"g1","changes":[
	    {"field":"Name","oldValue":"Wall A","newValue":"NewName"},
	    {"field":"Pset_WallCommon.FireRating","oldValue":"F30","newValue":"F90"}],
	   "author":"local-user","provenance":{"source":"UI"},"timestamp":"t","operation":"update"}]}`)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Migrated []struct {
			EntityID string `json:"entityId"`
			Field    string `json:"field"`
		} `json:"migrated"`
		Failed []struct {
			EntityID string `json:"entityId"`
			Field    string `json:"field"`
			Reason   string `json:"reason"`
		} `json:"failed"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if len(data.Failed) != 0 {
		t.Fatalf("failed = %+v", data.Failed)
	}
	if len(data.Migrated) != 2 {
		t.Fatalf("migrated = %+v", data.Migrated)
	}
	got := map[string]bool{}
	for _, m := range data.Migrated {
		got[m.EntityID+"/"+m.Field] = true
	}
	if !got["g1/Name"] || !got["g1/FireRating"] {
		t.Fatalf("migrated = %+v", data.Migrated)
	}

	// Python PUT body: Name → fields, FireRating → psets.Pset_WallCommon
	var putBody struct {
		Fields map[string]string            `json:"fields"`
		Psets  map[string]map[string]string `json:"psets"`
	}
	var commitBody string
	for _, c := range py.calls {
		switch c.Method {
		case "PUT":
			if err := json.Unmarshal([]byte(c.Body), &putBody); err != nil {
				t.Fatal(err)
			}
		case "POST":
			commitBody = c.Body
		}
	}
	if putBody.Fields["Name"] != "NewName" {
		t.Fatalf("put fields = %+v", putBody.Fields)
	}
	if putBody.Psets["Pset_WallCommon"]["FireRating"] != "F90" {
		t.Fatalf("put psets = %+v", putBody.Psets)
	}
	// commit body 带 operation=migrate（Python 侧 history 与 Go change log 一致）
	var cb struct {
		Operation string `json:"operation"`
	}
	if err := json.Unmarshal([]byte(commitBody), &cb); err != nil {
		t.Fatal(err)
	}
	if cb.Operation != "migrate" {
		t.Fatalf("commit body = %s, want operation=migrate", commitBody)
	}

	// override 清空
	all, err := env.ovr.GetAll(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 0 {
		t.Fatalf("overrides = %+v, want empty", all)
	}

	// change log：Operation=migrate，oldValue 为真原值
	entries, err := env.chg.List(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 {
		t.Fatalf("entries = %+v", entries)
	}
	byField := map[string]*change.Entry{}
	for _, en := range entries {
		byField[en.Field] = en
		if en.Operation != "migrate" {
			t.Fatalf("operation = %q, want migrate", en.Operation)
		}
	}
	if byField["Name"].OldValue != "Wall A" || byField["Name"].NewValue != "NewName" {
		t.Fatalf("Name entry = %+v", byField["Name"])
	}
	fr := byField["Pset_WallCommon.FireRating"]
	if fr == nil || fr.OldValue != "F30" || fr.NewValue != "F90" {
		t.Fatalf("FireRating entry = %+v", fr)
	}

	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestMigratePartialFailure(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	writeMetadata(t, env.st, env.modelID, testMetadata)
	// g1: Name 成功；g2: Classification 被 Python 422；g3: FireRating 但 metadata 无 pset
	if _, err := env.ovr.Set(env.modelID, "g1", map[string]string{"Name": "N1"}); err != nil {
		t.Fatal(err)
	}
	if _, err := env.ovr.Set(env.modelID, "g2", map[string]string{"Classification": "C1"}); err != nil {
		t.Fatal(err)
	}
	if _, err := env.ovr.Set(env.modelID, "g3", map[string]string{"FireRating": "F90"}); err != nil {
		t.Fatal(err)
	}
	py.set("PUT", "/models/"+env.modelID+"/entities/g1", 200,
		`{"id":"e_1","guid":"g1","changes":[],"author":"local-user","provenance":{"source":"UI"},"timestamp":"t"}`)
	py.set("PUT", "/models/"+env.modelID+"/entities/g2", 422, `{"detail":"unknown attribute: Classification"}`)
	py.set("POST", "/models/"+env.modelID+"/commit", 200, `{"committed":1,"entries":[
	  {"id":"e_1","guid":"g1","changes":[{"field":"Name","oldValue":"Old","newValue":"N1"}],
	   "author":"local-user","provenance":{"source":"UI"},"timestamp":"t","operation":"update"}]}`)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Migrated []struct {
			EntityID string `json:"entityId"`
			Field    string `json:"field"`
		} `json:"migrated"`
		Failed []struct {
			EntityID string `json:"entityId"`
			Field    string `json:"field"`
			Reason   string `json:"reason"`
		} `json:"failed"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if len(data.Migrated) != 1 || data.Migrated[0].EntityID != "g1" || data.Migrated[0].Field != "Name" {
		t.Fatalf("migrated = %+v", data.Migrated)
	}
	if len(data.Failed) != 2 {
		t.Fatalf("failed = %+v", data.Failed)
	}
	failByKey := map[string]string{}
	for _, f := range data.Failed {
		failByKey[f.EntityID+"/"+f.Field] = f.Reason
	}
	if r := failByKey["g2/Classification"]; !strings.Contains(r, "unknown attribute") {
		t.Fatalf("g2 reason = %q", r)
	}
	if r := failByKey["g3/FireRating"]; r == "" {
		t.Fatalf("g3 reason empty")
	}

	// 失败字段保留 override，成功字段清除
	all, err := env.ovr.GetAll(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 2 || all["g2"]["Classification"] != "C1" || all["g3"]["FireRating"] != "F90" {
		t.Fatalf("overrides = %+v", all)
	}
	if _, ok := all["g1"]; ok {
		t.Fatalf("g1 override should be cleared: %+v", all)
	}
	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestMigrateChangeLogFailureWarns(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnvChg(t, pyURL, failAppendChangeStore{err: errors.New("change log disk full")})
	writeMetadata(t, env.st, env.modelID, testMetadata)
	if _, err := env.ovr.Set(env.modelID, "g1", map[string]string{"Name": "NewName"}); err != nil {
		t.Fatal(err)
	}
	py.set("PUT", "/models/"+env.modelID+"/entities/g1", 200,
		`{"id":"e_1","guid":"g1","changes":[],"author":"local-user","provenance":{"source":"UI"},"timestamp":"t"}`)
	py.set("POST", "/models/"+env.modelID+"/commit", 200, `{"committed":1,"entries":[
	  {"id":"e_1","guid":"g1","changes":[{"field":"Name","oldValue":"Wall A","newValue":"NewName"}],
	   "author":"local-user","provenance":{"source":"UI"},"timestamp":"t","operation":"migrate"}]}`)

	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Migrated []struct {
			EntityID string `json:"entityId"`
			Field    string `json:"field"`
		} `json:"migrated"`
		Warning string `json:"warning"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if len(data.Migrated) != 1 {
		t.Fatalf("migrated = %+v", data.Migrated)
	}
	if !strings.Contains(data.Warning, "change log") {
		t.Fatalf("warning = %q, want change log failure surfaced", data.Warning)
	}
	// override 已清、重转已排
	all, err := env.ovr.GetAll(env.modelID)
	if err != nil {
		t.Fatal(err)
	}
	if len(all) != 0 {
		t.Fatalf("overrides = %+v, want empty", all)
	}
	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestMigrateEmptyOverrides(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	var data struct {
		Migrated []interface{} `json:"migrated"`
		Failed   []interface{} `json:"failed"`
	}
	if err := json.Unmarshal(e.Data, &data); err != nil {
		t.Fatal(err)
	}
	if data.Migrated == nil || data.Failed == nil || len(data.Migrated) != 0 || len(data.Failed) != 0 {
		t.Fatalf("data = %s, want {migrated:[],failed:[]}", e.Data)
	}
	if py.callCount() != 0 {
		t.Fatalf("python received %d calls, want 0", py.callCount())
	}
	assertNoRun(t, env.runs)
}

func TestEditEditableSchemaPassthrough(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	schema := `{"guid":"g1","ifcType":"IfcWall","fields":[{"name":"Name","kind":"string","value":"Wall A"},
	  {"name":"PredefinedType","kind":"enum","value":null,"enumValues":["STANDARD","NOTDEFINED"]}],
	  "psets":[{"name":"Pset_WallCommon","properties":[{"name":"FireRating","kind":"string","value":""}]}]}`
	py.set("GET", "/models/"+env.modelID+"/entities/g1/editable-schema", 200, schema)

	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/edit/entities/g1/editable-schema", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 {
		t.Fatalf("envelope code = %d msg = %s", e.Code, e.Message)
	}
	if !strings.Contains(string(e.Data), `"enumValues"`) || !strings.Contains(string(e.Data), `"Pset_WallCommon"`) {
		t.Fatalf("data = %s", e.Data)
	}
	call := py.lastCall()
	if call.Method != "GET" || call.Path != "/models/"+env.modelID+"/entities/g1/editable-schema" {
		t.Fatalf("call = %+v", call)
	}
}

func TestEditEditableSchemaStatusMapping(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("GET", "/models/"+env.modelID+"/entities/g9/editable-schema", 404, `{"detail":"entity not found"}`)
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/edit/entities/g9/editable-schema", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if e := decodeEnv(t, rec); e.Code != codeNotFound {
		t.Fatalf("code = %d, want %d", e.Code, codeNotFound)
	}
}

func TestEditDeleteEntityPassthrough(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	entry := `{"id":"e_del001","guid":"g1","action":"delete","changes":[
	  {"field":"__deleted__","oldValue":"Wall A","newValue":null}],
	  "author":"local-user","provenance":{"source":"UI"},"timestamp":"t"}`
	py.set("DELETE", "/models/"+env.modelID+"/entities/g1", 200, entry)

	body := `{"author":"local-user","provenance":{"source":"UI"}}`
	rec := doEditReq(t, env.mux, "DELETE", "/api/v1/models/"+env.modelID+"/edit/entities/g1", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 {
		t.Fatalf("envelope code = %d msg = %s", e.Code, e.Message)
	}
	var got map[string]interface{}
	if err := json.Unmarshal(e.Data, &got); err != nil {
		t.Fatal(err)
	}
	if got["action"] != "delete" || got["guid"] != "g1" {
		t.Fatalf("data = %s", e.Data)
	}
	call := py.lastCall()
	if call.Method != "DELETE" || call.Path != "/models/"+env.modelID+"/entities/g1" {
		t.Fatalf("call = %+v", call)
	}
	if call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
	}
}

func TestEditDeleteEntityEmptyBodyAllowed(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("DELETE", "/models/"+env.modelID+"/entities/g1", 200, `{"id":"e_1","guid":"g1","action":"delete"}`)
	rec := doEditReq(t, env.mux, "DELETE", "/api/v1/models/"+env.modelID+"/edit/entities/g1", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
}

func TestEditDeleteEntityBadProvenance(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	rec := doEditReq(t, env.mux, "DELETE", "/api/v1/models/"+env.modelID+"/edit/entities/g1",
		`{"provenance":{"source":"robot"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if e := decodeEnv(t, rec); e.Code != codeInvalidType {
		t.Fatalf("code = %d, want %d", e.Code, codeInvalidType)
	}
	if py.callCount() != 0 {
		t.Fatalf("python received %d calls, want 0", py.callCount())
	}
}

func TestEditDeleteEntityStatusMapping(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	cases := []struct {
		pyStatus   int
		wantStatus int
		wantCode   int
	}{
		{404, http.StatusNotFound, codeNotFound},
		{422, http.StatusBadRequest, codeInvalidType},
		{500, http.StatusBadGateway, codeBadGateway},
	}
	for _, c := range cases {
		py.set("DELETE", "/models/"+env.modelID+"/entities/g1", c.pyStatus, `{"detail":"boom"}`)
		rec := doEditReq(t, env.mux, "DELETE", "/api/v1/models/"+env.modelID+"/edit/entities/g1", "")
		if rec.Code != c.wantStatus {
			t.Fatalf("py %d: go status = %d, want %d (body %s)", c.pyStatus, rec.Code, c.wantStatus, rec.Body)
		}
		if e := decodeEnv(t, rec); e.Code != c.wantCode {
			t.Fatalf("py %d: envelope code = %d, want %d", c.pyStatus, e.Code, c.wantCode)
		}
	}
}

func TestMigrateBadProvenance(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	if _, err := env.ovr.Set(env.modelID, "g1", map[string]string{"Name": "N1"}); err != nil {
		t.Fatal(err)
	}
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/overrides/migrate",
		`{"provenance":{"source":"robot"}}`)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if py.callCount() != 0 {
		t.Fatalf("python received %d calls, want 0", py.callCount())
	}
}
