// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// mux_test.go：根 mux 子树分发契约（/api/v1/chat/ 与 /api/v1/projects/ 都归 chatHandler）。
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

// TestBuildRootMuxRouting 验证子树分发：方案/项目端点走 chatHandler（防 404 回归——
// 2026-08-21：/api/v1/projects/ 未注册到 chatHandler 时落 "/" 兜底 404）。
func TestBuildRootMuxRouting(t *testing.T) {
	chatHit := false
	rootHit := false
	chat := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		chatHit = true
		w.WriteHeader(http.StatusOK)
	})
	rootH := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rootHit = true
		w.WriteHeader(http.StatusOK)
	})
	mux := buildRootMux(chat, rootH)

	cases := []struct {
		path     string
		wantChat bool
	}{
		{"/api/v1/chat/projects", true},
		{"/api/v1/chat/sessions", true},
		{"/api/v1/chat/sessions/c_x/messages", true},
		{"/api/v1/projects/p_x/plan", true},
		{"/api/v1/projects/p_x/plan_history", true},
		{"/api/v1/projects/p_x/deliver", true},
		{"/api/v1/models", false},
		{"/api/v1/models/m_x/script", false},
		{"/", false},
	}
	for _, c := range cases {
		chatHit, rootHit = false, false
		mux.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest(http.MethodGet, c.path, nil))
		if c.wantChat && !chatHit {
			t.Errorf("%s 应走 chatHandler，走了 root", c.path)
		}
		if !c.wantChat && !rootHit {
			t.Errorf("%s 应走 root handler，走了 chat", c.path)
		}
	}
}
