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
// 豁免：OPTIONS 预检；GET /v1/models/ 下的只读模型文件（model.xkt / metadata.json /
// issues 截图），前端 xeokit 与 <img> 标签无法携带 Authorization 头，需匿名可读。
// 其余全部端点（含 GET /api/v1/models 列表与 chat 子树）要求 Authorization: Bearer <token>。
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
			got := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			if subtle.ConstantTimeCompare([]byte(got), []byte(token)) != 1 {
				writeErr(w, http.StatusUnauthorized, codeUnauthorized, "missing or invalid bearer token")
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

func isExemptReadOnly(r *http.Request) bool {
	return r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/v1/models/")
}
