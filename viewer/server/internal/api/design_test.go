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

// design 代理契约：edit-service 返回裸 JSON，Go 侧必须包 {code,message,data} envelope，
// data 原样透传；错误走 writeEditErr 的状态码映射（与 edit 代理一致）。

func designRoutes(modelID string) []struct {
	method string
	goPath string
	pyPath string
} {
	mk := func(method, suffix string) struct {
		method string
		goPath string
		pyPath string
	} {
		return struct {
			method string
			goPath string
			pyPath string
		}{method, "/api/v1/models/" + modelID + suffix, "/models/" + modelID + suffix}
	}
	return []struct {
		method string
		goPath string
		pyPath string
	}{
		mk("GET", "/design"),
		mk("PUT", "/design"),
		mk("POST", "/design/undo"),
		mk("POST", "/design/redo"),
		mk("POST", "/design/discard"),
		mk("POST", "/design/save"),
		mk("GET", "/designs"),
		mk("POST", "/design/rollback"),
		mk("POST", "/design/regenerate"),
		mk("POST", "/design/diff"),
		mk("POST", "/design/diff-ifc"),
	}
}

func TestDesignProxyEnvelope(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	mockBody := `{"modelId":"` + env.modelID + `","design":{"meta":{"name":"x"}}}`
	routes := designRoutes(env.modelID)
	if len(routes) != 11 {
		t.Fatalf("design routes = %d, want 11", len(routes))
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

func TestDesignProxyForwardsBody(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	py.set("PUT", "/models/"+env.modelID+"/design", 200, `{"staged":1}`)
	body := `{"design":{"meta":{}},"note":"n1"}`
	rec := doEditReq(t, env.mux, "PUT", "/api/v1/models/"+env.modelID+"/design", body)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if call := py.lastCall(); call.Body != body {
		t.Fatalf("forwarded body = %q, want %q", call.Body, body)
	}
}

func TestDesignProxyErrorMapping(t *testing.T) {
	py, pyURL := newFakePy(t)
	env := newEditEnv(t, pyURL)
	path := "/models/" + env.modelID + "/design"
	goPath := "/api/v1/models/" + env.modelID + "/design"
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
