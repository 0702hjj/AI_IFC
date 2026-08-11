// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"ifcviewer/server/internal/editsvc"
)

// chat_shell_test.go：notify 流程 Imperative Shell（chat_shell.go）的单测——补
// 端到端契约测试（chat_notify_test.go）未触及的分支：前置步骤失败 → notify_failed
// step 归一、resolveVersion 三态、runFailed 事件构造（step/reason 归一）。

// TestShellFrontStepFailureNotifiesFailed 断言 discard_pending / stage_script 失败 →
// 归一 viewer.notify_failed（step 正确）、fail-fast 不排重转。
func TestShellFrontStepFailureNotifiesFailed(t *testing.T) {
	cases := []struct {
		name     string
		wantStep string
	}{
		{"discard_pending", "discard_pending"},
		{"stage_script", "stage_script"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			py, pyURL := newFakePy(t)
			h, _, runs := newNotifyTestHandler(t, pyURL)
			cs := newNotifySession(t, h)
			mid := cs.ModelID

			if tc.wantStep == "stage_script" {
				py.set("DELETE", "/models/"+mid+"/pending", 200, `{"discarded":0}`)
				py.set("PUT", "/models/"+mid+"/script", 500, `{"detail":"stage boom"}`)
			} else {
				py.set("DELETE", "/models/"+mid+"/pending", 500, `{"detail":"pending boom"}`)
			}

			stagingDir := filepath.Join(h.deps.DataDir, "staging")
			if err := os.MkdirAll(stagingDir, 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(stagingDir, mid+".py"), []byte(notifySmokeScript), 0o644); err != nil {
				t.Fatal(err)
			}

			ch := h.subscribe(cs.ID)
			h.notify(cs)

			frame := waitChatEvent(t, ch, "viewer.notify_failed")
			if !strings.Contains(string(frame), `"step":"`+tc.wantStep+`"`) {
				t.Fatalf("notify_failed frame = %s, want step %s", frame, tc.wantStep)
			}
			if !strings.Contains(string(frame), `"reason"`) {
				t.Fatalf("notify_failed frame = %s, want reason", frame)
			}
			assertNoRun(t, runs)
		})
	}
}

// TestResolveVersion 断言 save 响应版本解析三态：带 version 直接成功（不触发兜底）、
// 兜底 GetVersions 成功、兜底失败 → save_version 显式失败（防空版本静默吞掉）。
func TestResolveVersion(t *testing.T) {
	t.Run("save_has_version_short_circuits_fallback", func(t *testing.T) {
		py, pyURL := newFakePy(t)
		ed := editsvc.New(pyURL)
		v, err := resolveVersion(context.Background(), ed, "m_x", []byte(`{"modelId":"m_x","version":"v7","staged":0}`))
		if err != nil {
			t.Fatalf("resolveVersion err = %v, want nil", err)
		}
		if v != "v7" {
			t.Fatalf("resolveVersion = %q, want v7", v)
		}
		if n := py.callCount(); n != 0 {
			t.Fatalf("save 响应带 version 不应触发 GetVersions 兜底，实际 %d 次调用", n)
		}
	})

	t.Run("fallback_get_versions_success", func(t *testing.T) {
		py, pyURL := newFakePy(t)
		ed := editsvc.New(pyURL)
		py.set("GET", "/models/m_x/versions", 200, `{"versions":[{"version":"v2","createdAt":"t1"}],"current":"v2"}`)
		v, err := resolveVersion(context.Background(), ed, "m_x", []byte(`{"modelId":"m_x","staged":0}`))
		if err != nil {
			t.Fatalf("resolveVersion err = %v, want nil", err)
		}
		if v != "v2" {
			t.Fatalf("resolveVersion = %q, want v2", v)
		}
	})

	t.Run("fallback_fails_returns_save_version_error", func(t *testing.T) {
		py, pyURL := newFakePy(t)
		ed := editsvc.New(pyURL)
		py.set("GET", "/models/m_x/versions", 500, `{"detail":"boom"}`)
		_, err := resolveVersion(context.Background(), ed, "m_x", []byte(`{"modelId":"m_x","staged":0}`))
		if err == nil {
			t.Fatal("兜底 GetVersions 失败应返回 save_version 错误")
		}
		if !strings.Contains(err.Error(), "GetVersions") {
			t.Fatalf("错误应指明兜底来源，got %v", err)
		}
	})

	t.Run("fallback_current_empty_returns_error", func(t *testing.T) {
		py, pyURL := newFakePy(t)
		ed := editsvc.New(pyURL)
		py.set("GET", "/models/m_x/versions", 200, `{"versions":[],"current":""}`)
		_, err := resolveVersion(context.Background(), ed, "m_x", []byte(`{"modelId":"m_x","staged":0}`))
		if err == nil {
			t.Fatal("兜底 current 为空应返回错误（防空版本被静默吞掉）")
		}
	})

	t.Run("undecodable_save_with_failed_fallback", func(t *testing.T) {
		py, pyURL := newFakePy(t)
		ed := editsvc.New(pyURL)
		py.set("GET", "/models/m_x/versions", 500, `{"detail":"boom"}`)
		_, err := resolveVersion(context.Background(), ed, "m_x", []byte(`not-json`))
		if err == nil {
			t.Fatal("save 响应非法且兜底失败应返回 save_version 错误")
		}
		if !strings.Contains(err.Error(), "decode save response") {
			t.Fatalf("错误应指明解码来源，got %v", err)
		}
	})
}

// TestRunFailedEventNormalization 断言 runFailed 把 step/reason 归一进 script/failed
// 事件并经 Core 决策推送 viewer.notify_failed（step/reason 原样透传）。
func TestRunFailedEventNormalization(t *testing.T) {
	h, _, _ := newNotifyTestHandler(t, "")
	cs := newNotifySession(t, h)
	ch := h.subscribe(cs.ID)

	h.runFailed(context.Background(), cs, "save_version", errors.New("version parse boom"))

	frame := waitChatEvent(t, ch, "viewer.notify_failed")
	if !strings.Contains(string(frame), `"step":"save_version"`) {
		t.Fatalf("notify_failed frame = %s, want step save_version", frame)
	}
	if !strings.Contains(string(frame), `"reason":"version parse boom"`) {
		t.Fatalf("notify_failed frame = %s, want reason version parse boom", frame)
	}
}
