// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"
)

// 静态托管（宿主直跑部署形态，替代原 nginx 容器）：Go server 直接服务 web/dist。
// 路由优先级：/api、/v1 前缀与非 GET/HEAD 一律转交 fallback（API handler）；
// 其余 GET/HEAD 命中 dist 文件即服务，未命中回退 index.html（React Router SPA fallback）。
// 缓存策略对齐原 web/nginx.conf：指纹资源（/assets/、/wasm/）长缓存 immutable，
// index.html 与其余文件 no-cache。
type staticHandler struct {
	dist     string
	fallback http.Handler
}

// NewStaticHandler 返回 SPA 静态托管 handler。distDir 为 web 构建产物目录；
// dist 缺失（未 npm run build）时静态路径返回 503，API 请求不受影响。
func NewStaticHandler(distDir string, fallback http.Handler) http.Handler {
	return &staticHandler{dist: distDir, fallback: fallback}
}

func (h *staticHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	p := r.URL.Path
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		h.fallback.ServeHTTP(w, r)
		return
	}
	if p == "/api" || p == "/v1" || strings.HasPrefix(p, "/api/") || strings.HasPrefix(p, "/v1/") {
		h.fallback.ServeHTTP(w, r)
		return
	}
	// dist 不可用（未构建）：降级 503，API 已在上方转交不受影响。
	index := filepath.Join(h.dist, "index.html")
	if _, err := os.Stat(index); err != nil {
		http.Error(w, "web frontend dist unavailable (run: cd web && npm run build); API is unaffected", http.StatusServiceUnavailable)
		return
	}
	// path.Clean 归一化（吸收 .. 段，防目录穿越）；命中文件则服务，否则 SPA 回退
	// index.html（r2.URL.Path 保留原请求路径，避免 ServeFile 的 index.html→./ 重定向）。
	clean := path.Clean("/" + p)
	name := filepath.Join(h.dist, filepath.FromSlash(clean))
	cachePath := clean
	if fi, err := os.Stat(name); err != nil || fi.IsDir() {
		name = index
		cachePath = "/index.html"
	}
	w.Header().Set("Cache-Control", staticCacheControl(cachePath))
	r2 := new(http.Request)
	*r2 = *r
	r2.URL.Path = clean
	http.ServeFile(w, r2, name)
}

// staticCacheControl：指纹资源（构建产物哈希名，/assets/ 与 /wasm/） immutable 长缓存；
// index.html 与其余文件 no-cache（发版后浏览器总能拿到新入口）。
func staticCacheControl(p string) string {
	if strings.HasPrefix(p, "/assets/") || strings.HasPrefix(p, "/wasm/") {
		return "public, max-age=31536000, immutable"
	}
	return "no-cache"
}
