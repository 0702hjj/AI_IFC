// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"crypto/subtle"
	"net/http"
	"strings"
)

const codeUnauthorized = 40100

// TokenAuth 返回最小 Bearer token 鉴权中间件。token 为空 = 鉴权关闭（单机零配置默认）。
// 豁免：OPTIONS 预检；GET /v1/models/ 下白名单内的只读模型文件（model.xkt /
// metadata.json / issues 截图），前端 xeokit 与 <img> 标签无法携带 Authorization 头，
// 需匿名可读。其余全部端点（含 GET /api/v1/models 列表与 chat 子树）要求
// Authorization: Bearer <token>（强制 Bearer scheme，裸 token 拒绝）。
// 例外：SSE events 端点（EventSource 无法携带自定义头）允许 ?token= query 回退。
func TokenAuth(token string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		if token == "" {
			return next
		}
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.Method == http.MethodOptions || isExemptReadOnly(r) {
				next.ServeHTTP(w, r)
				return
			}
			got := bearerToken(r.Header.Get("Authorization"))
			if got == "" && isSSEEvents(r) {
				got = r.URL.Query().Get("token")
			}
			if got == "" || subtle.ConstantTimeCompare([]byte(got), []byte(token)) != 1 {
				writeErr(w, http.StatusUnauthorized, codeUnauthorized, "missing or invalid bearer token")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

// bearerToken 提取 Authorization 头的 Bearer 凭证；无 "Bearer " 前缀返回空（拒绝裸 token）。
func bearerToken(h string) string {
	const prefix = "Bearer "
	if !strings.HasPrefix(h, prefix) {
		return ""
	}
	return strings.TrimPrefix(h, prefix)
}

// isSSEEvents 判定 chat SSE events 端点（EventSource 不支持自定义头，唯一允许 query token 的路径）。
func isSSEEvents(r *http.Request) bool {
	return r.Method == http.MethodGet &&
		strings.HasPrefix(r.URL.Path, "/api/v1/chat/sessions/") &&
		strings.HasSuffix(r.URL.Path, "/events")
}

// isExemptReadOnly 判定豁免的只读模型文件路由。白名单精确匹配（非前缀），
// 未来新增 /v1/models/ 路由默认受保护，防静默豁免（guard：TestAuthExemptWhitelistGuard）。
func isExemptReadOnly(r *http.Request) bool {
	if r.Method != http.MethodGet {
		return false
	}
	rest, ok := strings.CutPrefix(r.URL.Path, "/v1/models/")
	if !ok {
		return false
	}
	parts := strings.Split(rest, "/")
	if len(parts) == 2 && parts[0] != "" && (parts[1] == "model.xkt" || parts[1] == "metadata.json") {
		return true
	}
	return len(parts) == 3 && parts[0] != "" && parts[1] == "issues" && parts[2] != ""
}
