// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"ifcviewer/server/internal/change"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/issue"
	"ifcviewer/server/internal/override"
	"ifcviewer/server/internal/store"
)

func setupSecure(t *testing.T, token string, origins []string) (*httptest.Server, *store.Store) {
	t.Helper()
	st := store.NewStore(t.TempDir())
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q := convert.NewQueue(st, okRunner{}, 1)
	q.Start(ctx)
	h := NewHandlerWithCORS(st, q, issue.NewFileStore(st.DataDir), change.NewFileStore(st.DataDir), override.NewFileStore(st.DataDir), nil, 1<<20, origins)
	srv := httptest.NewServer(TokenAuth(token)(h))
	t.Cleanup(srv.Close)
	return srv, st
}

func do(t *testing.T, method, url, token, origin string) *http.Response {
	t.Helper()
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		t.Fatal(err)
	}
	if token != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}
	if origin != "" {
		req.Header.Set("Origin", origin)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { resp.Body.Close() })
	return resp
}

func TestAuthDisabledAllowsAnonymous(t *testing.T) {
	srv, _ := setupSecure(t, "", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("token 关闭时应放行: %d", resp.StatusCode)
	}
}

func TestAuthEnabledRejectsMissingToken(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("无 token 应 401: %d", resp.StatusCode)
	}
	body, _ := io.ReadAll(resp.Body)
	var e env
	if err := json.Unmarshal(body, &e); err != nil {
		t.Fatalf("401 应为 envelope: %v (%s)", err, body)
	}
	if e.Code != codeUnauthorized {
		t.Fatalf("错误码应为 %d: %+v", codeUnauthorized, e)
	}
}

func TestAuthEnabledRejectsWrongToken(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "wrong", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("错 token 应 401: %d", resp.StatusCode)
	}
}

func TestAuthEnabledAcceptsCorrectToken(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "s3cret", "")
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("正确 token 应放行: %d", resp.StatusCode)
	}
}

// 豁免清单：GET /v1/models/{id}/model.xkt|metadata.json、GET /v1/models/{id}/issues/{file}
// 为前端 xeokit/img 标签匿名可读（无法携带 Authorization 头）。
func TestAuthExemptsReadOnlyModelFiles(t *testing.T) {
	srv, st := setupSecure(t, "s3cret", nil)
	m, err := st.Create("a.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	for _, p := range []string{
		"/v1/models/" + m.ID + "/model.xkt",
		"/v1/models/" + m.ID + "/metadata.json",
		"/v1/models/" + m.ID + "/issues/i_0123456789ab.png",
	} {
		resp := do(t, "GET", srv.URL+p, "", "")
		if resp.StatusCode == http.StatusUnauthorized {
			t.Fatalf("豁免路径不应 401: %s", p)
		}
	}
}

// 非豁免的只读端点（模型列表）同样受保护。
func TestAuthProtectsModelList(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("模型列表应受保护: %d", resp.StatusCode)
	}
}

func TestAuthAllowsPreflightWithoutToken(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "OPTIONS", srv.URL+"/api/v1/models", "", "http://localhost:5173")
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("预检不应被鉴权拦截: %d", resp.StatusCode)
	}
}

func TestCORSReflectsWhitelistedOrigin(t *testing.T) {
	srv, _ := setupSecure(t, "", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "http://localhost:5173")
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "http://localhost:5173" {
		t.Fatalf("默认白名单 origin 应被反射: %q", got)
	}
}

func TestCORSDefaultIncludesPort8080(t *testing.T) {
	srv, _ := setupSecure(t, "", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "http://localhost:8080")
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "http://localhost:8080" {
		t.Fatalf("默认白名单应含 :8080: %q", got)
	}
}

func TestCORSDoesNotReflectUnknownOrigin(t *testing.T) {
	srv, _ := setupSecure(t, "", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "https://evil.example.com")
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("非白名单 origin 不应反射: %q", got)
	}
}

func TestCORSCustomWhitelist(t *testing.T) {
	srv, _ := setupSecure(t, "", []string{"https://ifc.example.com"})
	resp := do(t, "GET", srv.URL+"/api/v1/models", "", "https://ifc.example.com")
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "https://ifc.example.com" {
		t.Fatalf("自定义白名单 origin 应被反射: %q", got)
	}
	resp = do(t, "GET", srv.URL+"/api/v1/models", "", "http://localhost:5173")
	if got := resp.Header.Get("Access-Control-Allow-Origin"); got != "" {
		t.Fatalf("自定义白名单后默认 origin 不应反射: %q", got)
	}
}

func TestCORSPreflightAllowsAuthorizationHeader(t *testing.T) {
	srv, _ := setupSecure(t, "", nil)
	resp := do(t, "OPTIONS", srv.URL+"/api/v1/models", "", "http://localhost:5173")
	if resp.StatusCode != http.StatusNoContent {
		t.Fatalf("preflight: %d", resp.StatusCode)
	}
	if got := resp.Header.Get("Access-Control-Allow-Headers"); !strings.Contains(got, "Authorization") {
		t.Fatalf("Allow-Headers 应含 Authorization: %q", got)
	}
}
