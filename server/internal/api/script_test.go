// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/editsvc"
)

// script 代理契约：edit-service 返回裸 JSON，Go 侧必须包 {code,message,data} envelope，
// data 原样透传；错误走 writeEditErr 的状态码映射（与 edit 代理一致，P0-1 教训）。

func scriptRoutes(modelID string) []struct {
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
	}
}

func TestScriptProxyEnvelope(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"modelId":"` + env.modelID + `","script":"PARAMS = {}"}`
	routes := scriptRoutes(env.modelID)
	if len(routes) != 11 {
		t.Fatalf("script routes = %d, want 11", len(routes))
	}
	for _, rt := range routes {
		py.set(rt.method, rt.pyPath, 200, mockBody)
		body := ""
		if rt.method != "GET" {
			body = `{}`
		}
		rec := doEditReq(t, env.mux, rt.method, rt.goPath, body)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s %s: status = %d body = %s", rt.method, rt.goPath, rec.Code, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != 0 {
			t.Fatalf("%s %s: envelope code = %d (body %s)", rt.method, rt.goPath, e.Code, rec.Body)
		}
		if e.Message == "" {
			t.Fatalf("%s %s: envelope message empty (body %s)", rt.method, rt.goPath, rec.Body)
		}
		var got, want interface{}
		if err := json.Unmarshal(e.Data, &got); err != nil {
			t.Fatalf("%s %s: data not JSON: %v (data %s)", rt.method, rt.goPath, err, e.Data)
		}
		if err := json.Unmarshal([]byte(mockBody), &want); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("%s %s: data = %s, want %s", rt.method, rt.goPath, e.Data, mockBody)
		}
	}
}

func TestScriptProxyForwardsBody(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("PUT", "/models/"+env.modelID+"/script", 200, `{"staged":1}`)
	body := `{"script":"PARAMS = {}","note":"n1"}`
	rec := doEditReq(t, env.mux, "PUT", "/api/v1/models/"+env.modelID+"/script", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if call := py.lastCall(); call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
	}
}

func TestScriptProxySaveForwardsNote(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("POST", "/models/"+env.modelID+"/script/save", 200, `{"version":"v1"}`)
	body := `{"note":"checkpoint"}`
	rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/save", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if call := py.lastCall(); call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
	}
	e := decodeEnv(t, rec)
	var data map[string]string
	if err := json.Unmarshal(e.Data, &data); err != nil || data["version"] != "v1" {
		t.Fatalf("data = %s, want version v1", e.Data)
	}
	// save 成功会排 XKT 重转（异步写 models/{id}/），等其落地再结束，避免 TempDir 清理竞争
	waitRun(t, env.runs)
	waitReady(t, env.st, env.modelID)
}

func TestScriptProxyErrorMapping(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	path := "/models/" + env.modelID + "/script"
	goPath := "/api/v1/models/" + env.modelID + "/script"
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
		rec := doEditReq(t, env.mux, "GET", goPath, "")
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

// run/save/rollback 会让 edit-service 重写 uploads/{id}.ifc（routes_scripts.py
// _run_into_uploads），成功后必须 Enqueue 重转 XKT，否则前端 3D 永远不刷新（M5 缺口）。
func TestScriptMutatingActionsEnqueueReconvert(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	for _, action := range []string{"run", "save", "rollback"} {
		py.set("POST", "/models/"+env.modelID+"/script/"+action, 200, `{"ok":true}`)
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+action, `{}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d body = %s", action, rec.Code, rec.Body)
		}
		if in := waitRun(t, env.runs); !strings.Contains(in, env.modelID) {
			t.Fatalf("%s: runner input = %q, want model %s", action, in, env.modelID)
		}
		waitReady(t, env.st, env.modelID)
	}
}

// 不改 IFC 的动作（undo/redo/discard/diff）与只读端点不触发重转。
func TestScriptNonMutatingActionsNoEnqueue(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	for _, action := range []string{"undo", "redo", "discard", "diff"} {
		py.set("POST", "/models/"+env.modelID+"/script/"+action, 200, `{"ok":true}`)
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+action, `{}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d body = %s", action, rec.Code, rec.Body)
		}
	}
	assertNoRun(t, env.runs)
}

// edit-service 失败（4xx/5xx 透传）时不排重转。
func TestScriptMutatingActionFailureNoEnqueue(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	for _, c := range []struct {
		action   string
		pyStatus int
	}{
		{"save", 409},
		{"run", 500},
		{"rollback", 404},
	} {
		py.set("POST", "/models/"+env.modelID+"/script/"+c.action, c.pyStatus, `{"detail":"boom"}`)
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+c.action, `{}`)
		if rec.Code == http.StatusOK {
			t.Fatalf("%s py %d: go status = 200, want error (body %s)", c.action, c.pyStatus, rec.Body)
		}
	}
	assertNoRun(t, env.runs)
}

// run/save/rollback 的沙箱执行最长 60s（edit-service RUN_TIMEOUT_S=60s），Go 侧 fast
// client（10s）会先超时而 edit-service 继续跑完落盘 → 三方状态分叉（M5 终审 C2）。
// 用注入的短超时 + 延迟 mock 断言 client 选择：fast=50ms < delay < slow=2s。
func TestScriptSandboxActionsUseSlowClient(t *testing.T) {
	delay := 300 * time.Millisecond
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(delay)
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ok":true}`))
	}))
	t.Cleanup(srv.Close)
	env := newEditEnvWithClient(t, editsvc.NewWithTimeouts(srv.URL, 50*time.Millisecond, 2*time.Second), nil)

	// run/save/rollback 走 slow client：300ms 延迟下必须成功。
	for _, action := range []string{"run", "save", "rollback"} {
		rec := doEditReq(t, env.mux, "POST", "/api/v1/models/"+env.modelID+"/script/"+action, `{}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d, want 200（应走 slow client，body %s）", action, rec.Code, rec.Body)
		}
		waitRun(t, env.runs)
		waitReady(t, env.st, env.modelID)
	}
	// 只读端点保持 fast：同样的延迟必须超时（证明不是全局放宽超时）。
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/script", "")
	if rec.Code == http.StatusOK {
		t.Fatal("GET /script 应走 fast client 并在 300ms 延迟下超时，实际 200")
	}
}

// 小版本 diff（暂存链步间）：GET + query 透传，包 envelope（W-0012）。
func TestScriptStagingDiffProxy(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"from":0,"to":1,"text_diff":"--- step0\n+++ step1\n","params_changes":[],"stats":{"added":1,"removed":1}}`
	pyPath := "/models/" + env.modelID + "/script/staging/diff"
	goPath := "/api/v1/models/" + env.modelID + "/script/staging/diff"
	py.set("GET", pyPath, 200, mockBody)
	rec := doEditReq(t, env.mux, "GET", goPath+"?from=0&to=1", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if call := py.lastCall(); call.Path != pyPath || call.RawQuery != "from=0&to=1" {
		t.Fatalf("forwarded = %s?%s, want %s?from=0&to=1", call.Path, call.RawQuery, pyPath)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 || e.Message == "" {
		t.Fatalf("envelope = %+v", e)
	}
	var got, want interface{}
	if err := json.Unmarshal(e.Data, &got); err != nil {
		t.Fatalf("data not JSON: %v", err)
	}
	if err := json.Unmarshal([]byte(mockBody), &want); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("data = %s, want %s", e.Data, mockBody)
	}
}

// guid → 脚本调用点定位：GET + query（guid）原样透传，包 envelope（Task 9）。
func TestScriptLocateProxy(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"found":true,"designKey":"wall-1","line":12,"col":4,"snippet":"make_wall(key='wall-1')","origin":"params"}`
	pyPath := "/models/" + env.modelID + "/script/locate"
	goPath := "/api/v1/models/" + env.modelID + "/script/locate"
	py.set("GET", pyPath, 200, mockBody)
	rec := doEditReq(t, env.mux, "GET", goPath+"?guid=3abcDEF", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if call := py.lastCall(); call.Path != pyPath || call.RawQuery != "guid=3abcDEF" {
		t.Fatalf("forwarded = %s?%s, want %s?guid=3abcDEF", call.Path, call.RawQuery, pyPath)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 || e.Message == "" {
		t.Fatalf("envelope = %+v", e)
	}
	var got, want interface{}
	if err := json.Unmarshal(e.Data, &got); err != nil {
		t.Fatalf("data not JSON: %v", err)
	}
	if err := json.Unmarshal([]byte(mockBody), &want); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("data = %s, want %s", e.Data, mockBody)
	}
}

// locate miss（found:false）也是 200 契约，不映射为错误（契约违规属 bug，不 5xx）。
func TestScriptLocateMissPassthrough(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("GET", "/models/"+env.modelID+"/script/locate", 200, `{"found":false}`)
	rec := doEditReq(t, env.mux, "GET", "/api/v1/models/"+env.modelID+"/script/locate?guid=x", "")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	e := decodeEnv(t, rec)
	if e.Code != 0 {
		t.Fatalf("envelope code = %d, want 0", e.Code)
	}
	var data map[string]interface{}
	if err := json.Unmarshal(e.Data, &data); err != nil || data["found"] != false {
		t.Fatalf("data = %s, want found=false", e.Data)
	}
}
