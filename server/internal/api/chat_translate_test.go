// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/agent"
)

// --- 翻译层：agent Event → 浏览器消费的 opencode 形状 SSE 帧（逐字段对拍 ChatSidebar 契约） ---

func ev(t *testing.T, evType string, turn, step int, payload map[string]any) agent.Event {
	t.Helper()
	raw, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	return agent.Event{Type: evType, Turn: turn, Step: step, Payload: raw, Ts: time.Now()}
}

// frameData 解一帧的 data JSON 为 map。
func frameData(t *testing.T, f translatedFrame) map[string]any {
	t.Helper()
	raw, err := json.Marshal(f.data)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

// TestTranslateTurnStart：turn/start → session.status busy + 用户消息 message.updated。
func TestTranslateTurnStart(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventTurnStart, 1, 0, map[string]any{"user": "hi"}))
	if len(frames) != 2 {
		t.Fatalf("frames = %d, want 2: %v", len(frames), frames)
	}
	if frames[0].event != "session.status" {
		t.Fatalf("frames[0] = %s, want session.status", frames[0].event)
	}
	d := frameData(t, frames[0])
	if st, _ := d["status"].(map[string]any); st["type"] != "busy" {
		t.Fatalf("status.type = %v, want busy", d)
	}
	if frames[1].event != "message.updated" {
		t.Fatalf("frames[1] = %s, want message.updated", frames[1].event)
	}
	info, _ := frameData(t, frames[1])["info"].(map[string]any)
	if info["role"] != "user" || info["id"] == "" {
		t.Fatalf("user message.updated info = %v", info)
	}
}

// TestTranslateAssistantChunks：首个 content 分片先建 text part 行（空文本）再发 delta；
// 后续分片只发 delta——对齐 ChatSidebar「建行不覆盖、delta 累加」契约。
func TestTranslateAssistantChunks(t *testing.T) {
	tr := newEventTranslator("s_abc")
	var frames []translatedFrame
	frames = append(frames, tr.translate(ev(t, agent.EventStepStart, 1, 1, map[string]any{"kind": "model"}))...)
	frames = append(frames, tr.translate(ev(t, agent.EventAssistantChunk, 1, 1, map[string]any{"content": "你好"}))...)
	frames = append(frames, tr.translate(ev(t, agent.EventAssistantChunk, 1, 1, map[string]any{"content": "，世界"}))...)

	var kinds []string
	for _, f := range frames {
		kinds = append(kinds, f.event)
	}
	want := []string{"message.updated", "message.part.updated", "message.part.delta", "message.part.delta"}
	if strings.Join(kinds, "|") != strings.Join(want, "|") {
		t.Fatalf("events = %v, want %v", kinds, want)
	}
	// message.updated 建立 assistant 角色
	info, _ := frameData(t, frames[0])["info"].(map[string]any)
	if info["role"] != "assistant" {
		t.Fatalf("step/start 应建 assistant message.updated: %v", info)
	}
	msgID, _ := info["id"].(string)
	// part.updated：text 类型、空文本（增量走 delta）
	part, _ := frameData(t, frames[1])["part"].(map[string]any)
	if part["type"] != "text" || part["messageID"] != msgID || part["text"] != "" {
		t.Fatalf("首个分片的 part.updated = %v, want text/空文本/messageID=%s", part, msgID)
	}
	partID, _ := part["id"].(string)
	// 两条 delta：field=text、partID 稳定、delta 逐片
	for i, wantDelta := range []string{"你好", "，世界"} {
		d := frameData(t, frames[2+i])
		if d["sessionID"] != "s_abc" || d["messageID"] != msgID || d["partID"] != partID ||
			d["field"] != "text" || d["delta"] != wantDelta {
			t.Fatalf("delta[%d] = %v, want partID=%s delta=%q", i, d, partID, wantDelta)
		}
	}
}

// TestTranslateReasoningChunk：reasoning 分片走独立 reasoning part（前端可折叠段）。
func TestTranslateReasoningChunk(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventAssistantChunk, 1, 1, map[string]any{"reasoning": "先想想"}))
	if len(frames) != 2 || frames[0].event != "message.part.updated" || frames[1].event != "message.part.delta" {
		t.Fatalf("reasoning 分片帧序列 = %v", frames)
	}
	part, _ := frameData(t, frames[0])["part"].(map[string]any)
	if part["type"] != "reasoning" {
		t.Fatalf("reasoning part type = %v", part["type"])
	}
	d := frameData(t, frames[1])
	if d["field"] != "text" || d["delta"] != "先想想" || d["partID"] != part["id"] {
		t.Fatalf("reasoning delta = %v", d)
	}
}

// TestTranslateAssistantMessageNonStreamed：无分片直达的 assistant/message（内容非空）
// 建 text part 行并带全量文本；已有分片建行后不重复建行（防覆盖 delta 累加）。
func TestTranslateAssistantMessageNonStreamed(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventAssistantMessage, 1, 1, map[string]any{"content": "完整答复"}))
	if len(frames) != 1 || frames[0].event != "message.part.updated" {
		t.Fatalf("frames = %v, want 单条 part.updated", frames)
	}
	part, _ := frameData(t, frames[0])["part"].(map[string]any)
	if part["type"] != "text" || part["text"] != "完整答复" {
		t.Fatalf("part = %v, want 全量文本", part)
	}

	// 同 part 已有分片建行 → assistant/message 不再建行
	tr2 := newEventTranslator("s_abc")
	tr2.translate(ev(t, agent.EventAssistantChunk, 1, 1, map[string]any{"content": "片"}))
	frames = tr2.translate(ev(t, agent.EventAssistantMessage, 1, 1, map[string]any{"content": "片"}))
	if len(frames) != 0 {
		t.Fatalf("已建行的 part 不应重复 part.updated: %v", frames)
	}
}

// TestTranslateToolCallAndResult：tool/call → running 卡片（带 input）；
// tool/result → 同 part 更新 completed + output，input 保留（跨 step 经 call id 配对）。
func TestTranslateToolCallAndResult(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventToolCall, 1, 1,
		map[string]any{"id": "call-1", "name": "write", "arguments": `{"path":"a.ifc"}`}))
	if len(frames) != 1 || frames[0].event != "message.part.updated" {
		t.Fatalf("tool/call frames = %v", frames)
	}
	part, _ := frameData(t, frames[0])["part"].(map[string]any)
	if part["type"] != "tool" || part["tool"] != "write" {
		t.Fatalf("tool part = %v", part)
	}
	st, _ := part["state"].(map[string]any)
	if st["status"] != "running" || st["title"] == "" || st["input"] != `{"path":"a.ifc"}` {
		t.Fatalf("running state = %v", st)
	}
	partID, _ := part["id"].(string)

	// result 在后续 step 到达，仍更新同一 part
	frames = tr.translate(ev(t, agent.EventToolResult, 1, 2,
		map[string]any{"id": "call-1", "name": "write", "content": "ok"}))
	if len(frames) != 1 || frames[0].event != "message.part.updated" {
		t.Fatalf("tool/result frames = %v", frames)
	}
	part2, _ := frameData(t, frames[0])["part"].(map[string]any)
	if part2["id"] != partID {
		t.Fatalf("result part id = %v, want %s（同一张卡片更新）", part2["id"], partID)
	}
	st2, _ := part2["state"].(map[string]any)
	if st2["status"] != "completed" || st2["output"] != "ok" || st2["input"] != `{"path":"a.ifc"}` {
		t.Fatalf("completed state = %v, want output + 保留 input", st2)
	}
}

// TestTranslateErrorAndTurnEnd：error → session.error；turn/end → session.status idle + session.idle。
func TestTranslateErrorAndTurnEnd(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventError, 1, 2, map[string]any{"error": "boom"}))
	if len(frames) != 1 || frames[0].event != "session.error" {
		t.Fatalf("error frames = %v", frames)
	}
	if d := frameData(t, frames[0]); d["error"] != "boom" {
		t.Fatalf("session.error data = %v", d)
	}

	frames = tr.translate(ev(t, agent.EventTurnEnd, 1, 0, map[string]any{"message": "done"}))
	if len(frames) != 2 || frames[0].event != "session.status" || frames[1].event != "session.idle" {
		t.Fatalf("turn/end frames = %v, want session.status + session.idle", frames)
	}
	if st, _ := frameData(t, frames[0])["status"].(map[string]any); st["type"] != "idle" {
		t.Fatalf("status = %v, want idle", st)
	}
}

// --- 历史回填 projection：事件日志 → ChatSidebar fetchChatMessages 消费的 {info, parts} 形状 ---

// TestProjectChatHistory：一轮含工具调用的完整事件序列投影为 opencode 形状历史：
// user(text) → assistant(text+tool completed) → assistant(final text)。
func TestProjectChatHistory(t *testing.T) {
	evs := []agent.Event{
		ev(t, agent.EventTurnStart, 1, 0, map[string]any{"user": "把墙改宽"}),
		ev(t, agent.EventStepStart, 1, 1, map[string]any{"kind": "model"}),
		ev(t, agent.EventAssistantMessage, 1, 1, map[string]any{
			"content": "", "tool_calls": []map[string]any{{"id": "call-1", "name": "write", "arguments": `{"w":5}`}},
		}),
		ev(t, agent.EventToolCall, 1, 1, map[string]any{"id": "call-1", "name": "write", "arguments": `{"w":5}`}),
		ev(t, agent.EventStepStart, 1, 2, map[string]any{"kind": "tool", "name": "write"}),
		ev(t, agent.EventToolResult, 1, 2, map[string]any{"id": "call-1", "name": "write", "content": "saved"}),
		ev(t, agent.EventStepStart, 1, 3, map[string]any{"kind": "model"}),
		ev(t, agent.EventAssistantChunk, 1, 3, map[string]any{"content": "已改"}),
		ev(t, agent.EventAssistantMessage, 1, 3, map[string]any{"content": "已改"}),
		ev(t, agent.EventTurnEnd, 1, 0, map[string]any{"message": "已改"}),
	}
	msgs := projectChatHistory(evs, "s_abc")
	if len(msgs) != 3 {
		t.Fatalf("msgs = %d, want 3: %v", len(msgs), msgs)
	}
	// user：text part 带原文（前端跳过 user 的 SSE part，但历史必须还原）
	if msgs[0].Info["role"] != "user" || msgs[0].Info["id"] == "" {
		t.Fatalf("user info = %v", msgs[0].Info)
	}
	up := msgs[0].Parts[0]
	if up["type"] != "text" || up["text"] != "把墙改宽" || up["id"] == "" {
		t.Fatalf("user part = %v", up)
	}
	// assistant 1：tool part（completed + input/output）
	if msgs[1].Info["role"] != "assistant" {
		t.Fatalf("msg1 info = %v", msgs[1].Info)
	}
	var toolPart map[string]any
	for _, p := range msgs[1].Parts {
		if p["type"] == "tool" {
			toolPart = p
		}
	}
	if toolPart == nil {
		t.Fatalf("msg1 缺 tool part: %v", msgs[1].Parts)
	}
	if toolPart["tool"] != "write" || toolPart["id"] == "" {
		t.Fatalf("tool part = %v", toolPart)
	}
	st, _ := toolPart["state"].(map[string]any)
	if st["status"] != "completed" || st["input"] != `{"w":5}` || st["output"] != "saved" {
		t.Fatalf("tool state = %v", st)
	}
	// assistant 2：text part 全量文本（delta 不重复计数）
	tp := msgs[2].Parts[0]
	if tp["type"] != "text" || tp["text"] != "已改" {
		t.Fatalf("final text part = %v", tp)
	}
}

// TestProjectChatHistoryMultiTurn：两轮对话投影顺序与角色正确（turn 编号递增）。
func TestProjectChatHistoryMultiTurn(t *testing.T) {
	mk := func(turn int, user, answer string) []agent.Event {
		return []agent.Event{
			ev(t, agent.EventTurnStart, turn, 0, map[string]any{"user": user}),
			ev(t, agent.EventStepStart, turn, 1, map[string]any{"kind": "model"}),
			ev(t, agent.EventAssistantMessage, turn, 1, map[string]any{"content": answer}),
			ev(t, agent.EventTurnEnd, turn, 0, map[string]any{"message": answer}),
		}
	}
	msgs := projectChatHistory(append(mk(1, "q1", "a1"), mk(2, "q2", "a2")...), "s_x")
	if len(msgs) != 4 {
		t.Fatalf("msgs = %d, want 4", len(msgs))
	}
	want := []struct{ role, text string }{
		{"user", "q1"}, {"assistant", "a1"}, {"user", "q2"}, {"assistant", "a2"},
	}
	for i, w := range want {
		if msgs[i].Info["role"] != w.role || msgs[i].Parts[0]["text"] != w.text {
			t.Errorf("msg%d = %v/%v, want %s/%s", i, msgs[i].Info["role"], msgs[i].Parts[0]["text"], w.role, w.text)
		}
	}
	if msgs[0].Info["id"] == msgs[2].Info["id"] {
		t.Errorf("两轮的 user 消息 id 应不同: %v", msgs[0].Info["id"])
	}
}

// TestTranslateQuestionAsk D3a：EventQuestionAsk → question.ask SSE 帧。
func TestTranslateQuestionAsk(t *testing.T) {
	tr := newEventTranslator("s_abc")
	frames := tr.translate(ev(t, agent.EventQuestionAsk, 1, 0, map[string]any{
		"interruptId": "i-123", "question": "是否确认以 3 米层高保存？",
	}))
	if len(frames) != 1 || frames[0].event != "question.ask" {
		t.Fatalf("frames = %+v, want 1 question.ask", frames)
	}
	d := frameData(t, frames[0])
	if strOf(d, "interruptId") != "i-123" || strOf(d, "question") == "" {
		t.Fatalf("question.ask payload = %v", d)
	}
}
