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

// 附带小项（W-0010）：强制 Bearer scheme——裸 token（无 "Bearer " 前缀）必须拒绝。
func TestAuthRejectsBareTokenWithoutBearerScheme(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	req, err := http.NewRequest("GET", srv.URL+"/api/v1/models", nil)
	if err != nil {
		t.Fatal(err)
	}
	req.Header.Set("Authorization", "s3cret")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { resp.Body.Close() })
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("裸 token（无 Bearer scheme）应 401: %d", resp.StatusCode)
	}
}

// SSE 回退（W-0010）：EventSource 无法携带自定义头，仅 chat events 路径允许 ?token= 传 token。
func TestAuthAcceptsQueryTokenForSSEEventsPath(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/chat/sessions/c_nope/events?token=s3cret", "", "")
	if resp.StatusCode == http.StatusUnauthorized {
		t.Fatalf("events 路径带正确 query token 不应 401: %d", resp.StatusCode)
	}
}

func TestAuthRejectsWrongQueryTokenForSSEEventsPath(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/chat/sessions/c_nope/events?token=wrong", "", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("events 路径带错 query token 应 401: %d", resp.StatusCode)
	}
}

func TestAuthRejectsQueryTokenOnNonSSEPath(t *testing.T) {
	srv, _ := setupSecure(t, "s3cret", nil)
	resp := do(t, "GET", srv.URL+"/api/v1/models?token=s3cret", "", "")
	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("非 events 路径不允许 query token 回退: %d", resp.StatusCode)
	}
}

// 豁免白名单 guard（W-0010）：当前豁免路由仅以下三条——
//   GET /v1/models/{id}/model.xkt
//   GET /v1/models/{id}/metadata.json
//   GET /v1/models/{id}/issues/{file}
// 其余 /v1/models/ 下的 GET 一律 401。未来新增 /v1/models/ 路由默认受保护；
// 若确需匿名豁免，必须显式扩充白名单并同步更新本测试清单。
func TestAuthExemptWhitelistGuard(t *testing.T) {
	srv, st := setupSecure(t, "s3cret", nil)
	m, err := st.Create("a.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	for _, p := range []string{
		"/v1/models/" + m.ID + "/evil.bin",
		"/v1/models/" + m.ID + "/issues",
		"/v1/models/" + m.ID + "/model.xkt.bak",
		"/v1/models/" + m.ID,
		"/v1/models/",
	} {
		resp := do(t, "GET", srv.URL+p, "", "")
		if resp.StatusCode != http.StatusUnauthorized {
			t.Fatalf("白名单外路径应 401（防前缀静默豁免）: %s -> %d", p, resp.StatusCode)
		}
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
