// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools_error_test.go：工具错误单卡映射——翻译层（error 载荷 tool/result
// → 工具卡片 status:"error"）与历史投影（重开会话错误卡片仍在）。
package api

import (
	"testing"

	"ifcviewer/server/internal/agent"
)

// --- 工具错误单卡映射（翻译层 + 历史投影） ---

// TestTranslateToolErrorSingleCard：error 载荷的 tool/result → 工具卡片
// status:"error" + error 字段（前端 ✗ 状态），不再只靠 session.error 横幅。
func TestTranslateToolErrorSingleCard(t *testing.T) {
	tr := newEventTranslator("s_abc")
	var frames []translatedFrame
	frames = append(frames, tr.translate(ev(t, agent.EventToolCall, 1, 1,
		map[string]any{"id": "call-9", "name": "run_script", "arguments": `{}`}))...)
	frames = append(frames, tr.translate(ev(t, agent.EventToolResult, 1, 2,
		map[string]any{"id": "call-9", "name": "run_script", "error": "沙箱执行失败"}))...)
	if len(frames) != 2 {
		t.Fatalf("frames = %d, want 2", len(frames))
	}
	part, _ := frameData(t, frames[1])["part"].(map[string]any)
	st, _ := part["state"].(map[string]any)
	if st["status"] != "error" {
		t.Fatalf("state.status = %v, want error", st)
	}
	if st["error"] != "沙箱执行失败" {
		t.Fatalf("state.error = %v", st)
	}
	if _, has := st["output"]; has {
		t.Fatalf("错误态不应带 output: %v", st)
	}
	if st["input"] != `{}` {
		t.Fatalf("state.input = %v, want 保留调用参数", st)
	}
}

// TestProjectHistoryToolErrorState：历史投影同样折叠出 error 状态卡片
// （重新打开会话时错误卡片仍在）。
func TestProjectHistoryToolErrorState(t *testing.T) {
	evs := []agent.Event{
		ev(t, agent.EventTurnStart, 1, 0, map[string]any{"user": "跑一下"}),
		ev(t, agent.EventAssistantMessage, 1, 1, map[string]any{"content": ""}),
		ev(t, agent.EventToolCall, 1, 1, map[string]any{"id": "call-9", "name": "run_script", "arguments": `{}`}),
		ev(t, agent.EventToolResult, 1, 2, map[string]any{"id": "call-9", "name": "run_script", "error": "kaboom"}),
	}
	msgs := projectChatHistory(evs, "s_abc")
	var sawErr bool
	for _, m := range msgs {
		for _, p := range m.Parts {
			if p["type"] != "tool" {
				continue
			}
			st, _ := p["state"].(map[string]any)
			if st != nil && st["status"] == "error" && st["error"] == "kaboom" {
				sawErr = true
			}
		}
	}
	if !sawErr {
		t.Fatalf("历史投影未保留工具错误卡片: %v", msgs)
	}
}
