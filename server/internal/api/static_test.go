// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// writeDist 在临时目录搭一个最小 web dist 构建产物。
func writeDist(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	files := map[string]string{
		"index.html":            "<html><body>aiifc-spa</body></html>",
		"assets/app-a1b2c3d4.js": "console.log(1)",
		"wasm/web-ifc.wasm":     "wasm-bytes",
		"favicon.svg":           "<svg/>",
	}
	for name, body := range files {
		p := filepath.Join(dir, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

// fallbackStub 记录是否被调用（验证 API 路径不被静态托管 shadow）。
type fallbackStub struct{ hits []string }

func (f *fallbackStub) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.hits = append(f.hits, r.Method+" "+r.URL.Path)
	w.Header().Set("X-Fallback", "1")
	w.WriteHeader(http.StatusTeapot)
}

func doStatic(t *testing.T, h http.Handler, method, path string) *httptest.ResponseRecorder {
	t.Helper()
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, httptest.NewRequest(method, path, nil))
	return rec
}

func TestStaticServesIndexAtRoot(t *testing.T) {
	fb := &fallbackStub{}
	h := NewStaticHandler(writeDist(t), fb)

	rec := doStatic(t, h, "GET", "/")
	if rec.Code != http.StatusOK {
		t.Fatalf("GET / = %d, want 200", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "aiifc-spa") {
		t.Fatalf("GET / 未返回 index.html: %q", rec.Body.String())
	}
	if len(fb.hits) != 0 {
		t.Fatalf("根路径不应落到 API fallback: %v", fb.hits)
	}
}

func TestStaticSPAFallbackToIndex(t *testing.T) {
	fb := &fallbackStub{}
	h := NewStaticHandler(writeDist(t), fb)

	// React Router 客户端路由（无对应文件）回退 index.html。
	for _, p := range []string{"/models", "/models/m_0123456789abcdef", "/chat/abc"} {
		rec := doStatic(t, h, "GET", p)
		if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "aiifc-spa") {
			t.Fatalf("GET %s 应回退 index.html，got %d %q", p, rec.Code, rec.Body.String())
		}
		if cc := rec.Header().Get("Cache-Control"); cc != "no-cache" {
			t.Fatalf("index.html 缓存头 = %q, want no-cache", cc)
		}
	}
	if len(fb.hits) != 0 {
		t.Fatalf("SPA 路径不应落到 API fallback: %v", fb.hits)
	}
}

func TestStaticFingerprintAssetsLongCache(t *testing.T) {
	fb := &fallbackStub{}
	h := NewStaticHandler(writeDist(t), fb)

	for _, p := range []string{"/assets/app-a1b2c3d4.js", "/wasm/web-ifc.wasm"} {
		rec := doStatic(t, h, "GET", p)
		if rec.Code != http.StatusOK {
			t.Fatalf("GET %s = %d, want 200", p, rec.Code)
		}
		if cc := rec.Header().Get("Cache-Control"); cc != "public, max-age=31536000, immutable" {
			t.Fatalf("指纹资源缓存头 = %q, want immutable 长缓存", cc)
		}
	}
	// 非指纹静态文件（favicon）不长缓存。
	rec := doStatic(t, h, "GET", "/favicon.svg")
	if rec.Code != http.StatusOK {
		t.Fatalf("GET /favicon.svg = %d", rec.Code)
	}
	if cc := rec.Header().Get("Cache-Control"); cc != "no-cache" {
		t.Fatalf("favicon 缓存头 = %q, want no-cache", cc)
	}
}

func TestStaticDoesNotShadowAPI(t *testing.T) {
	fb := &fallbackStub{}
	h := NewStaticHandler(writeDist(t), fb)

	// /api 与 /v1 前缀一律转交 API handler（即便 GET 且 dist 里无同名文件）。
	for _, p := range []string{"/api/v1/models", "/v1/models/m_0123456789abcdef/model.xkt"} {
		rec := doStatic(t, h, "GET", p)
		if rec.Header().Get("X-Fallback") != "1" {
			t.Fatalf("GET %s 未转交 API fallback（code=%d）", p, rec.Code)
		}
	}
	// 非 GET/HEAD 一律转交（POST /api/... 不能被静态层吞掉）。
	rec := doStatic(t, h, "POST", "/api/v1/models")
	if rec.Header().Get("X-Fallback") != "1" {
		t.Fatalf("POST /api/v1/models 未转交 API fallback（code=%d）", rec.Code)
	}
	// 非 GET 的非 API 路径也转交（由 API mux 决定 404/405）。
	rec = doStatic(t, h, "POST", "/models")
	if rec.Header().Get("X-Fallback") != "1" {
		t.Fatalf("POST /models 未转交 fallback（code=%d）", rec.Code)
	}
}

func TestStaticPathTraversalStaysInDist(t *testing.T) {
	fb := &fallbackStub{}
	dist := writeDist(t)
	h := NewStaticHandler(dist, fb)

	// 路径穿越不得逃逸 dist：回退 index.html 而不是读到 dist 外文件。
	rec := doStatic(t, h, "GET", "/../static_test.go")
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "aiifc-spa") {
		t.Fatalf("穿越路径应回退 index.html，got %d %q", rec.Code, rec.Body.String())
	}
}

func TestStaticMissingDistDegrades503(t *testing.T) {
	fb := &fallbackStub{}
	h := NewStaticHandler(filepath.Join(t.TempDir(), "no-such-dist"), fb)

	// dist 缺失：静态路径 503 且不 panic。
	for _, p := range []string{"/", "/models", "/assets/app.js"} {
		rec := doStatic(t, h, "GET", p)
		if rec.Code != http.StatusServiceUnavailable {
			t.Fatalf("dist 缺失时 GET %s = %d, want 503", p, rec.Code)
		}
	}
	// API 照常转交。
	rec := doStatic(t, h, "GET", "/api/v1/models")
	if rec.Header().Get("X-Fallback") != "1" {
		t.Fatalf("dist 缺失时 API 不应受影响（code=%d）", rec.Code)
	}
}
