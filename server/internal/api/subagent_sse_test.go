// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// subagent SSE 契约测试：subagent.status 事件帧形状、子 part 帧附加 subagentId
// 字段（主会话帧不带——附加字段不破坏 ChatSidebar 既有解析）、端到端派发帧序。
package api

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"testing"

	"github.com/cloudwego/eino/components/model"

	"ifcviewer/server/internal/agent"
)

// --- 翻译层 ---

// TestTranslateSubagentStatus：subagent/status → event "subagent.status"，data
// 含 subagentId/parentSessionId/persona/status/task 五字段。
func TestTranslateSubagentStatus(t *testing.T) {
	tr := newEventTranslator("s_abc")
	for _, status := range []string{"started", "finished"} {
		frames := tr.translate(ev(t, agent.EventSubagentStatus, 1, 1, map[string]any{
			"subagentId": "sa_1_1", "parentSessionId": "s_abc",
			"persona": agent.PersonaIFC, "status": status, "task": "建墙",
		}))
		if len(frames) != 1 {
			t.Fatalf("status=%s frames = %d, want 1", status, len(frames))
		}
		if frames[0].event != "subagent.status" {
			t.Fatalf("event 名 = %s, want subagent.status", frames[0].event)
		}
		d := frameData(t, frames[0])
		if d["subagentId"] != "sa_1_1" || d["parentSessionId"] != "s_abc" ||
			d["persona"] != agent.PersonaIFC || d["status"] != status || d["task"] != "建墙" {
			t.Fatalf("subagent.status data = %v", d)
		}
	}
}

// TestTranslateChildPartCarriesSubagentID：子 agent 的 part 级帧 data 附加
// subagentId 字段（tool 卡片 + text part + delta），主会话同名帧不带该字段。
func TestTranslateChildPartCarriesSubagentID(t *testing.T) {
	tr := newEventTranslator("s_abc")

	// 主会话事件：任何帧都不带 subagentId
	frames := tr.translate(ev(t, agent.EventToolCall, 1, 1, map[string]any{
		"id": "cc-1", "name": "get_script", "arguments": `{}`,
	}))
	frames = append(frames, tr.translate(ev(t, agent.EventAssistantMessage, 1, 2, map[string]any{
		"content": "主的答复",
	}))...)
	if len(frames) == 0 {
		t.Fatal("主事件未产出帧")
	}
	for _, f := range frames {
		d := frameData(t, f)
		if _, has := d["subagentId"]; has {
			t.Fatalf("主会话帧不应带 subagentId: %s %v", f.event, d)
		}
	}

	// 子事件（Event.SubagentID 非空）：part 帧与 chunk 帧都附加 subagentId
	subTool := agent.Event{Type: agent.EventToolCall, Turn: 1, Step: 3, SubagentID: "sa_1_1",
		Payload: json.RawMessage(`{"id":"cc-2","name":"get_script","arguments":"{}"}`)}
	subFrames := tr.translate(subTool)
	if len(subFrames) != 1 {
		t.Fatalf("子 tool/call frames = %d, want 1", len(subFrames))
	}
	if d := frameData(t, subFrames[0]); d["subagentId"] != "sa_1_1" {
		t.Fatalf("子 part 帧 data.subagentId = %v, want sa_1_1", d)
	}

	subText := agent.Event{Type: agent.EventAssistantChunk, Turn: 1, Step: 4, SubagentID: "sa_1_1",
		Payload: json.RawMessage(`{"content":"子的文本"}`)}
	for _, f := range tr.translate(subText) {
		d := frameData(t, f)
		if d["subagentId"] != "sa_1_1" {
			t.Fatalf("子 chunk 帧 data.subagentId = %v, want sa_1_1（%s）", d, f.event)
		}
	}
}

// TestHistoryProjectionSubagentParts：历史投影跳过子事件（子内容在右侧边栏
// 由 subagent 分组承载，不进主会话消息流）。
func TestHistoryProjectionSubagentParts(t *testing.T) {
	evs := []agent.Event{
		ev(t, agent.EventTurnStart, 1, 0, map[string]any{"user": "go"}),
		{Type: agent.EventSubagentStatus, Turn: 1, SubagentID: "sa_1_1",
			Payload: json.RawMessage(`{"status":"started","persona":"ifc-agent"}`)},
		{Type: agent.EventToolCall, Turn: 1, Step: 1, SubagentID: "sa_1_1",
			Payload: json.RawMessage(`{"id":"cc-1","name":"get_script","arguments":"{}"}`)},
		{Type: agent.EventAssistantMessage, Turn: 1, Step: 2, SubagentID: "sa_1_1",
			Payload: json.RawMessage(`{"content":"子的正文"}`)},
		ev(t, agent.EventToolCall, 1, 1, map[string]any{"id": "d1", "name": "dispatch_ifc_agent", "arguments": `{"task":"x"}`}),
		ev(t, agent.EventAssistantMessage, 1, 3, map[string]any{"content": "主答复"}),
	}
	msgs := projectChatHistory(evs, "s_abc")
	var sawChild bool
	for _, m := range msgs {
		for _, p := range m.Parts {
			if txt, _ := p["text"].(string); txt == "子的正文" {
				sawChild = true
			}
		}
	}
	if sawChild {
		t.Fatalf("子事件泄漏进主会话历史投影: %v", msgs)
	}
	if len(msgs) < 2 {
		t.Fatalf("主会话投影应保留 user + assistant: %v", msgs)
	}
}

// --- 端到端：SSE 帧序（scripted 主 agent 派发 → 子 run → 汇总） ---

// subagentScript 一次子 agent run：先调 list_models（St 缺失 → 错误文本化，
// 不中断子 run），再收尾答复。
func subagentScript() agent.Script {
	return agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "cc-1", Name: "list_models", Arguments: `{}`}}},
		{Chunks: []string{"子代理执行完毕"}},
	}}
}

// newSubagentHandler 构造带 subagent 派发工具的 scripted handler（主 agent 工具面
// 只有 dispatch_ifc_agent；子工具面 = DomainTools，其中 list_models 因 St 缺失错误
// 文本化——端到端契约只关心事件流形状）。
func newSubagentHandler(t *testing.T) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	evStore := agent.NewEventStore(dataDir)
	h := &ChatHandler{
		deps:     ChatDeps{Ev: evStore, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	// 主 agent 工具面 = 领域工具 + 派发工具；子模型每次派发新建 scripted 实例，
	// 子工具面 = DomainTools（list_models 因 St 缺失错误文本化，不影响事件流契约）
	subNewModel := func() model.ToolCallingChatModel { return agent.NewScriptedModel(subagentScript()) }
	ag, err := agent.New(agent.LLMConfig{},
		agent.WithModel(agent.NewScriptedModel(agent.Script{Steps: []agent.ScriptStep{
			{ToolCalls: []agent.ToolCallSpec{{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":"生成标准层平面"}`}}},
			{Chunks: []string{"已派发并汇总"}},
		}})),
		agent.WithStore(evStore),
		agent.WithTools(h.SubagentAgentTools(agent.LLMConfig{}, subNewModel)),
	)
	if err != nil {
		t.Fatalf("agent.New: %v", err)
	}
	h.SetAgent(ag)
	return h
}

// TestSubagentSSEFlowEndToEnd：post 一条消息，scripted 主 agent 派发 ifc 子
// agent，浏览器应收到：subagent.status(started) → 子 part 帧（带 subagentId）
// → subagent.status(finished) → 主 dispatch 工具卡 → session.idle。
func TestSubagentSSEFlowEndToEnd(t *testing.T) {
	h := newSubagentHandler(t)
	cs, err := doChatCreate(h, `{"title":"t"}`)
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "画个平面"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	frames := collectUntil(t, ch, "session.idle")

	var started, finished bool
	for _, f := range frames {
		if strings.Contains(f, "event: subagent.status") && strings.Contains(f, `"status":"started"`) {
			started = true
		}
		if strings.Contains(f, "event: subagent.status") && strings.Contains(f, `"status":"finished"`) {
			finished = true
		}
	}
	if !started || !finished {
		t.Fatalf("缺 subagent.status started=%v finished=%v:\n%s", started, finished, strings.Join(frames, "---\n"))
	}
	// 子 part 帧带 subagentId
	var sawChildPart bool
	for _, f := range frames {
		if strings.Contains(f, "event: message.part.updated") && strings.Contains(f, `"subagentId":"sa_1_1"`) {
			sawChildPart = true
		}
	}
	if !sawChildPart {
		t.Fatal("未见带 subagentId 的子 part 帧")
	}
	// dispatch 工具结果携带子最终答复（汇总纪律：主 agent 转述子报告）
	if !strings.Contains(strings.Join(frames, "\n"), "子代理执行完毕") {
		t.Fatal("dispatch 工具结果应包含子最终答复")
	}
}
