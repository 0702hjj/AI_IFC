// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"net/http"
	"reflect"
	"strings"
	"testing"
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
		mk("GET", "/scripts", "/scripts"),
	}
}

func TestScriptProxyEnvelope(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"modelId":"` + env.modelID + `","script":"PARAMS = {}"}`
	routes := scriptRoutes(env.modelID)
	if len(routes) != 10 {
		t.Fatalf("script routes = %d, want 10", len(routes))
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

// design diff 代理（W-0012 前保留）：只剩 diff / diff-ifc 两个端点。
func TestDesignDiffProxyEnvelope(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"base":"v1","target":"v2","engine":"design-json"}`
	for _, action := range []string{"diff", "diff-ifc"} {
		pyPath := "/models/" + env.modelID + "/design/" + action
		goPath := "/api/v1/models/" + env.modelID + "/design/" + action
		py.set("POST", pyPath, 200, mockBody)
		rec := doEditReq(t, env.mux, "POST", goPath, `{"base":"v1","target":"v2"}`)
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d body = %s", goPath, rec.Code, rec.Body)
		}
		e := decodeEnv(t, rec)
		if e.Code != 0 || e.Message == "" {
			t.Fatalf("%s: envelope = %+v", goPath, e)
		}
		var got, want interface{}
		if err := json.Unmarshal(e.Data, &got); err != nil {
			t.Fatalf("%s: data not JSON: %v", goPath, err)
		}
		if err := json.Unmarshal([]byte(mockBody), &want); err != nil {
			t.Fatal(err)
		}
		if !reflect.DeepEqual(got, want) {
			t.Fatalf("%s: data = %s, want %s", goPath, e.Data, mockBody)
		}
	}
}
