package agent

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func fixedTs() time.Time { return time.Date(2026, 8, 14, 10, 0, 0, 0, time.UTC) }

func payloadOf(t *testing.T, v any) json.RawMessage {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}
	return raw
}

func TestEventStoreAppendLoadRoundTrip(t *testing.T) {
	dir := t.TempDir()
	st := NewEventStore(dir)

	evs := []Event{
		{Type: EventTurnStart, Turn: 1, Payload: payloadOf(t, map[string]any{"user": "hi"}), Ts: fixedTs()},
		{Type: EventStepStart, Turn: 1, Step: 1, Payload: payloadOf(t, map[string]any{"kind": "model"}), Ts: fixedTs().Add(time.Second)},
		{Type: EventAssistantMessage, Turn: 1, Step: 1, Payload: payloadOf(t, map[string]any{"content": "hello"}), Ts: fixedTs().Add(2 * time.Second)},
		{Type: EventTurnEnd, Turn: 1, Payload: payloadOf(t, map[string]any{"message": "hello"}), Ts: fixedTs().Add(3 * time.Second)},
	}
	for _, ev := range evs {
		if err := st.Append("sess-1", ev); err != nil {
			t.Fatalf("Append: %v", err)
		}
	}

	loaded, err := st.Load("sess-1")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if len(loaded) != len(evs) {
		t.Fatalf("Load returned %d events, want %d", len(loaded), len(evs))
	}
	for i := range evs {
		if loaded[i].Type != evs[i].Type || loaded[i].Turn != evs[i].Turn || loaded[i].Step != evs[i].Step {
			t.Errorf("event %d mismatch: got %+v want %+v", i, loaded[i], evs[i])
		}
		if !loaded[i].Ts.Equal(evs[i].Ts) {
			t.Errorf("event %d ts mismatch: got %v want %v", i, loaded[i].Ts, evs[i].Ts)
		}
		if string(loaded[i].Payload) != string(evs[i].Payload) {
			t.Errorf("event %d payload mismatch: got %s want %s", i, loaded[i].Payload, evs[i].Payload)
		}
	}

	raw, err := os.ReadFile(filepath.Join(dir, "chat", "sess-1.jsonl"))
	if err != nil {
		t.Fatalf("read log: %v", err)
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if len(lines) != len(evs)+1 {
		t.Fatalf("log has %d lines, want %d (header + events)", len(lines), len(evs)+1)
	}
	var header map[string]any
	if err := json.Unmarshal([]byte(lines[0]), &header); err != nil {
		t.Fatalf("header line not JSON: %v", err)
	}
	if header["type"] != "header" || header["session"] != "sess-1" {
		t.Errorf("unexpected header: %v", header)
	}
}

func TestEventStoreLoadMissing(t *testing.T) {
	st := NewEventStore(t.TempDir())
	evs, err := st.Load("nope")
	if err != nil {
		t.Fatalf("Load missing: %v", err)
	}
	if len(evs) != 0 {
		t.Fatalf("Load missing returned %d events, want 0", len(evs))
	}
}

func TestEventStoreRejectsBadSessionID(t *testing.T) {
	st := NewEventStore(t.TempDir())
	ev := Event{Type: EventTurnStart, Turn: 1, Ts: fixedTs()}
	for _, bad := range []string{"", "../escape", "a/b", `a\b`, ".", ".."} {
		if err := st.Append(bad, ev); err == nil {
			t.Errorf("Append(%q) succeeded, want error", bad)
		}
		if _, err := st.Load(bad); err == nil {
			t.Errorf("Load(%q) succeeded, want error", bad)
		}
	}
}

func TestProjectFoldsMessages(t *testing.T) {
	toolCalls := []map[string]any{{"id": "call-1", "name": "echo", "arguments": `{"text":"hi"}`}}
	evs := []Event{
		{Type: EventTurnStart, Turn: 1, Payload: payloadOf(t, map[string]any{"user": "你好"})},
		{Type: EventStepStart, Turn: 1, Step: 1, Payload: payloadOf(t, map[string]any{"kind": "model"})},
		{Type: EventAssistantMessage, Turn: 1, Step: 1, Payload: payloadOf(t, map[string]any{"content": "", "tool_calls": toolCalls})},
		{Type: EventToolCall, Turn: 1, Step: 1, Payload: payloadOf(t, map[string]any{"id": "call-1", "name": "echo", "arguments": `{"text":"hi"}`})},
		{Type: EventToolResult, Turn: 1, Step: 2, Payload: payloadOf(t, map[string]any{"id": "call-1", "name": "echo", "content": "hi"})},
		{Type: EventAssistantMessage, Turn: 1, Step: 3, Payload: payloadOf(t, map[string]any{"content": "最终答复"})},
		{Type: EventTurnEnd, Turn: 1, Payload: payloadOf(t, map[string]any{"message": "最终答复"})},
	}

	msgs := Project(evs)
	if len(msgs) != 4 {
		t.Fatalf("Project returned %d messages, want 4: %v", len(msgs), msgs)
	}
	if msgs[0]["role"] != "user" || msgs[0]["content"] != "你好" {
		t.Errorf("msg0 = %v", msgs[0])
	}
	if msgs[1]["role"] != "assistant" {
		t.Errorf("msg1 = %v", msgs[1])
	}
	calls, ok := msgs[1]["tool_calls"].([]any)
	if !ok || len(calls) != 1 {
		t.Fatalf("msg1 tool_calls = %v", msgs[1]["tool_calls"])
	}
	if call, ok := calls[0].(map[string]any); !ok || call["name"] != "echo" {
		t.Errorf("msg1 tool_calls[0] = %v", calls[0])
	}
	if msgs[2]["role"] != "tool" || msgs[2]["tool_call_id"] != "call-1" || msgs[2]["content"] != "hi" {
		t.Errorf("msg2 = %v", msgs[2])
	}
	if msgs[3]["role"] != "assistant" || msgs[3]["content"] != "最终答复" {
		t.Errorf("msg3 = %v", msgs[3])
	}
	if _, has := msgs[3]["tool_calls"]; has {
		t.Errorf("msg3 should not carry tool_calls: %v", msgs[3])
	}
}

func TestProjectMultipleTurns(t *testing.T) {
	mk := func(turn int, user, answer string) []Event {
		return []Event{
			{Type: EventTurnStart, Turn: turn, Payload: payloadOf(t, map[string]any{"user": user})},
			{Type: EventAssistantMessage, Turn: turn, Step: 1, Payload: payloadOf(t, map[string]any{"content": answer})},
			{Type: EventTurnEnd, Turn: turn, Payload: payloadOf(t, map[string]any{"message": answer})},
		}
	}
	evs := append(mk(1, "q1", "a1"), mk(2, "q2", "a2")...)
	msgs := Project(evs)
	if len(msgs) != 4 {
		t.Fatalf("Project returned %d messages, want 4", len(msgs))
	}
	want := []struct{ role, content string }{
		{"user", "q1"}, {"assistant", "a1"}, {"user", "q2"}, {"assistant", "a2"},
	}
	for i, w := range want {
		if msgs[i]["role"] != w.role || msgs[i]["content"] != w.content {
			t.Errorf("msg%d = %v, want %s/%s", i, msgs[i], w.role, w.content)
		}
	}
}
