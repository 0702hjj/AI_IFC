// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/override"
	"ifcviewer/server/internal/store"
)

// cad 代理契约（W-0040）：模型 kind=dxf 时 script/edit 代理面整体转向 services/cad
// （:8200），路由表与 ifc 完全同构——同一批 /api/v1/models/{id}/script* 端点按
// kind 分流到不同后端。edit-call 不出现在 Go 路由表（服务直连纪律同 IFC）。

// newCadEnvWithClient 建 dxf 模型 + 双 client（ed=services/ifc, cad=services/cad），
// 返回带 runs 侦察通道的 env。dxf 模型 Create 即 ready（无转换）。
func newCadEnvWithClient(t *testing.T, ed, cad *editsvc.Client) *editEnv {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	runs := make(chan string, 4)
	q := convert.NewQueue(st, spyRunner{runs: runs}, 1)
	q.Start(ctx)
	mux := NewHandler(st, q, issue.NewFileStore(st.DataDir), change.NewFileStore(st.DataDir),
		override.NewFileStore(st.DataDir), ed, cad, 1<<20)
	m, err := st.CreateWithKind("ok.dxf", 4, strings.NewReader("fake"), store.KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	return &editEnv{mux: mux, modelID: m.ID, st: st, q: q, runs: runs}
}

func newCadEnv(t *testing.T) (*editEnv, *fakePy, *fakePy) {
	t.Helper()
	edPy, edURL := newFakePy(t)
	cadPy, cadURL := newFakePy(t)
	env := newCadEnvWithClient(t, editsvc.New(edURL), editsvc.New(cadURL))
	return env, edPy, cadPy
}

// cadRoutes 是 dxf 模型的代理面：script 11 端点 + versions + diff（edit-call 除外）。
func cadRoutes(modelID string) []struct {
	method string
	goPath string
	pyPath string
} {
	mk := func(method, goSuffix, pySuffix string) struct {
		method string
		goPath string
		pyPath string
	} {
		return struct {
			method string
			goPath string
			pyPath string
		}{method, "/api/v1/models/" + modelID + goSuffix, "/models/" + modelID + pySuffix}
	}
	return []struct {
		method string
		goPath string
		pyPath string
	}{
		mk("GET", "/script", "/script"),
		mk("PUT", "/script", "/script"),
		mk("GET", "/script/params", "/script/params"),
		mk("POST", "/script/undo", "/script/undo"),
		mk("POST", "/script/redo", "/script/redo"),
		mk("POST", "/script/discard", "/script/discard"),
		mk("POST", "/script/run", "/script/run"),
		mk("POST", "/script/save", "/script/save"),
		mk("POST", "/script/rollback", "/script/rollback"),
		mk("POST", "/script/diff", "/script/diff"),
		mk("GET", "/scripts", "/scripts"),
		mk("GET", "/edit/versions", "/versions"),
		mk("POST", "/edit/diff", "/diff"),
	}
}

// 全代理面包 envelope、透传 data、打到 services/cad；ifc 后端零调用。
func TestCadProxyEnvelope(t *testing.T) {
	env, edPy, cadPy := newCadEnv(t)
	routes := cadRoutes(env.modelID)
	if len(routes) != 13 {
		t.Fatalf("cad routes = %d, want 13", len(routes))
	}
	for _, rt := range routes {
		// versions 走 typed decode（editsvc.Versions）再包 envelope，用同形 body。
		mockBody := `{"modelId":"` + env.modelID + `","ok":true}`
		if strings.HasSuffix(rt.pyPath, "/versions") {
			mockBody = fakeVersionsBody
		}
		cadPy.set(rt.method, rt.pyPath, 200, mockBody)
		body := ""
		if rt.method != "GET" {
			body = `{}`
		}
		rec := doEditReq(t, env.mux, rt.method, rt.goPath, body)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s %s: status = %d body = %s", rt.method, rt.goPath, rec.Code, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != 0 || e.Message == "" {
			t.Fatalf("%s %s: envelope = %+v", rt.method, rt.goPath, e)
		}
		var got, want interface{}
		if err := json.Unmarshal(e.Data, &got); err != nil {
			t.Fatalf("%s %s: data not JSON: %v", rt.method, rt.goPath, err)
		}
		if err := json.Unmarshal([]byte(mockBody), &want); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("%s %s: data = %s, want %s", rt.method, rt.goPath, e.Data, mockBody)
		}
		if call := cadPy.lastCall(); call.Path != rt.pyPath {
			t.Fatalf("%s %s: cad received %s, want %s", rt.method, rt.goPath, call.Path, rt.pyPath)
		}
	}
	if n := edPy.callCount(); n != 0 {
		t.Fatalf("ifc edit-service received %d calls, want 0（dxf 模型不应打到 :8100）", n)
	}
	assertNoRun(t, env.runs)
}

// 错误翻译与 ifc 代理同映射（writeEditErr 共享）。
func TestCadProxyErrorMapping(t *testing.T) {
	env, _, cadPy := newCadEnv(t)
	pyPath := "/models/" + env.modelID + "/script"
	goPath := "/api/v1/models/" + env.modelID + "/script"
	for _, c := range []struct {
		pyStatus   int
		wantStatus int
		wantCode   int
	}{
		{404, http.StatusNotFound, codeNotFound},
		{409, http.StatusConflict, codeConflict},
		{422, http.StatusBadRequest, codeInvalidType},
		{500, http.StatusBadGateway, codeBadGateway},
	} {
		cadPy.set("GET", pyPath, c.pyStatus, `{"detail":"boom"}`)
		rec := doEditReq(t, env.mux, "GET", goPath, "")
		if rec.Code != c.wantStatus {
			t.Fatalf("py %d: go status = %d, want %d (body %s)", c.pyStatus, rec.Code, c.wantStatus, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != c.wantCode || !strings.Contains(e.Message, "boom") {
			t.Fatalf("py %d: envelope = %+v", c.pyStatus, e)
		}
	}
}

// dxf kind 的 mutating 动作（run/save/rollback）代理成功但不触发 XKT 重转——
// XKT 是 ifc 专属产物（W-0040 硬口径）。
func TestCadMutatingActionsNoReconvert(t *testing.T) {
	env, _, cadPy := newCadEnv(t)
	for _, action := range []string{"run", "save", "rollback"} {
		cadPy.set("POST", "/models/"+env.modelID+"/script/"+action, 200, `{"ok":true}`)
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+action, `{}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d body = %s", action, rec.Code, rec.Body)
		}
	}
	assertNoRun(t, env.runs)
	m, err := env.st.Get(env.modelID)
	if err != nil || m.Status != "ready" {
		t.Fatalf("status = %q, want ready（dxf 不应被置 converting）", m.Status)
	}
}

// dxf 的 run/save/rollback 同样走 slow client（cad 沙箱执行同 60s 量级）；
// 只读端点保持 fast。断言方式同 ifc 侧（M5 终审 C2 教训）。
func TestCadSandboxActionsUseSlowClient(t *testing.T) {
	delay := 300 * time.Millisecond
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(delay)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ok":true}`))
	}))
	t.Cleanup(srv.Close)
	env := newCadEnvWithClient(t, nil, editsvc.NewWithTimeouts(srv.URL, 50*time.Millisecond, 2*time.Second))

	for _, action := range []string{"run", "save", "rollback"} {
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+action, `{}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d, want 200（应走 slow client，body %s）", action, rec.Code, rec.Body)
		}
	}
	assertNoRun(t, env.runs)
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/script", "")
	if rec.Code == http.StatusOK {
		t.Fatal("GET /script 应走 fast client 并在 300ms 延迟下超时，实际 200")
	}
}

// ifc 模型回归：kind=ifc 仍打 services/ifc，cad 后端零调用。
func TestIFCScriptRoutesToEditService(t *testing.T) {
	env, edPy, cadPy := newCadEnv(t)
	ifc, err := env.st.Create("ok.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	if err := env.st.SetStatus(ifc.ID, "ready", ""); err != nil {
		t.Fatal(err)
	}
	edPy.set("GET", "/models/"+ifc.ID+"/script", 200, `{"script":"PARAMS = {}"}`)
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+ifc.ID+"/script", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if n := edPy.callCount(); n != 1 {
		t.Fatalf("edit-service calls = %d, want 1", n)
	}
	if n := cadPy.callCount(); n != 0 {
		t.Fatalf("cad service received %d calls, want 0（ifc 模型不应打到 :8200）", n)
	}
}

// kind 分流需要 Go 侧先取模型：未知模型 404（不再透传到后端服务）。
func TestScriptProxyUnknownModel404(t *testing.T) {
	env, edPy, cadPy := newCadEnv(t)
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/m_0000000000000000/script", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404 (body %s)", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != codeNotFound {
		t.Fatalf("envelope code = %d, want %d", e.Code, codeNotFound)
	}
	if edPy.callCount()+cadPy.callCount() != 0 {
		t.Fatal("未知模型不应打到任何后端服务")
	}
}

// edit-call 按 spec 仅服务直连暴露：Go 路由表不注册 → mux 404（两 kind 同）。
func TestEditCallRouteNotRegistered(t *testing.T) {
	env, _, _ := newCadEnv(t)
	for _, id := range []string{env.modelID} {
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+id+"/script/edit-call", `{}`)
		if rec.Code != http.StatusNotFound {
			t.Fatalf("status = %d, want 404（edit-call 不经 Go 代理；body %s）", rec.Code, rec.Body)
		}
	}
	ifcEnv := newEditEnv(t, "")
	rec := doEditReq(t, ifcEnv.mux, "POST", "/api/v1/models/"+ifcEnv.modelID+"/script/edit-call", `{}`)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("ifc: status = %d, want 404（body %s）", rec.Code, rec.Body)
	}
}

func uploadToMux(t *testing.T, mux http.Handler, filename, content string) *httptest.ResponseRecorder {
	t.Helper()
	var body strings.Builder
	w := multipart.NewWriter(&body)
	fw, err := w.CreateFormFile("file", filename)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := fw.Write([]byte(content)); err != nil {
		t.Fatal(err)
	}
	if err := w.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest("POST", "/api/v1/models", strings.NewReader(body.String()))
	req.Header.Set("Content-Type", w.FormDataContentType())
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, req)
	return rec
}

func decodeUploaded(t *testing.T, rec *httptest.ResponseRecorder) store.Model {
	t.Helper()
	e := decodeEnv(t, rec)
	if e.Code != 0 {
		t.Fatalf("envelope = %+v", e)
	}
	var m store.Model
	if err := json.Unmarshal(e.Data, &m); err != nil {
		t.Fatalf("data decode: %v", err)
	}
	return m
}

// .dxf 上传：kind=dxf、直接 ready、不进 converter 队列；download 回 .dxf 源文件。
func TestUploadDXFKindReadyNoConvert(t *testing.T) {
	env, _, _ := newCadEnv(t)
	rec := uploadToMux(t, env.mux, "plan.dxf", "0\nSECTION\n")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body)
	}
	m := decodeUploaded(t, rec)
	if m.Kind != store.KindDXF {
		t.Fatalf("kind = %q, want %q", m.Kind, store.KindDXF)
	}
	if m.Status != "ready" {
		t.Fatalf("status = %q, want ready（dxf 无转换）", m.Status)
	}
	assertNoRun(t, env.runs)

	rec = doEditReq(t, env.mux, "GET", "/api/v1/models/"+m.ID+"/download", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("download: %d", rec.Code)
	}
	if cd := rec.Header().Get("Content-Disposition"); !strings.Contains(cd, "plan.dxf") {
		t.Fatalf("Content-Disposition = %q, want plan.dxf", cd)
	}
	if rec.Body.String() != "0\nSECTION\n" {
		t.Fatalf("download body = %q", rec.Body.String())
	}
}

// .ifc 上传回归：kind=ifc、converting、入队转换（spy runner 立即成功转 ready）。
func TestUploadIFCUnchanged(t *testing.T) {
	env, _, _ := newCadEnv(t)
	rec := uploadToMux(t, env.mux, "ok.ifc", "ISO-10303-21;fake")
	if rec.Code != http.StatusOK {
		t.Fatalf("upload: %d %s", rec.Code, rec.Body)
	}
	m := decodeUploaded(t, rec)
	if m.Kind != store.KindIFC {
		t.Fatalf("kind = %q, want %q", m.Kind, store.KindIFC)
	}
	if in := waitRun(t, env.runs); !strings.Contains(in, m.ID) {
		t.Fatalf("runner input = %q, want model %s", in, m.ID)
	}
	waitReady(t, env.st, m.ID)
}

// 白名单外扩展名仍 400 codeInvalidType（domain 哨兵错误 → handler 翻译）。
func TestUploadUnsupportedExtRejected(t *testing.T) {
	env, _, _ := newCadEnv(t)
	rec := uploadToMux(t, env.mux, "a.txt", "x")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400 (body %s)", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != codeInvalidType {
		t.Fatalf("envelope code = %d, want %d", e.Code, codeInvalidType)
	}
}

// dxf 模型 retry（异常进入 failed 的恢复路径）：回 ready 且不入队转换。
func TestRetryDXFNoConvert(t *testing.T) {
	env, _, _ := newCadEnv(t)
	if err := env.st.SetStatus(env.modelID, "failed", "boom"); err != nil {
		t.Fatal(err)
	}
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/retry", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("retry: %d %s", rec.Code, rec.Body)
	}
	m := decodeUploaded(t, rec)
	if m.Status != "ready" {
		t.Fatalf("status = %q, want ready（dxf 无转换可重试）", m.Status)
	}
	assertNoRun(t, env.runs)
}

// render.json 只读端点（serveModelFile 模式，与 model.xkt 同族）：已发布的
// payload 文件直接下发；缺失 → 404。
func TestRenderJSONServed(t *testing.T) {
	env, _, _ := newCadEnv(t)
	payload := `{"version":2,"entities":[]}`
	if err := os.WriteFile(filepath.Join(env.st.ModelDir(env.modelID), "render.json"), []byte(payload), 0o644); err != nil {
		t.Fatal(err)
	}
	rec := doEditReq(t, env.mux, "GET", "/v1/models/"+env.modelID+"/render.json", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d, want 200", rec.Code)
	}
	if rec.Body.String() != payload {
		t.Fatalf("body = %q, want %q", rec.Body.String(), payload)
	}

	rec = doEditReq(t, env.mux, "GET", "/v1/models/m_0000000000000000/render.json", "")
	if rec.Code != http.StatusNotFound {
		t.Fatalf("unknown model: status = %d, want 404", rec.Code)
	}
}
