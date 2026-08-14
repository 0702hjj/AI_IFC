package agent

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/components/tool/utils"
)

type echoReq struct {
	Text string `json:"text" jsonschema:"required,description=要回显的文本"`
}

func echoTool(t *testing.T) tool.BaseTool {
	t.Helper()
	tl, err := utils.InferTool("echo", "回显输入文本",
		func(ctx context.Context, in echoReq) (string, error) {
			return in.Text, nil
		})
	if err != nil {
		t.Fatalf("InferTool: %v", err)
	}
	return tl
}

func roundTripScript() Script {
	return Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "call-1", Name: "echo", Arguments: `{"text":"hello"}`}}},
		{Chunks: []string{"done"}},
	}}
}

func collect(t *testing.T, ch <-chan Event) []Event {
	t.Helper()
	var evs []Event
	for ev := range ch {
		evs = append(evs, ev)
	}
	if len(evs) == 0 {
		t.Fatalf("no events emitted")
	}
	return evs
}

func eventTypes(evs []Event) []string {
	types := make([]string, len(evs))
	for i, ev := range evs {
		types[i] = ev.Type
	}
	return types
}

func payloadString(t *testing.T, ev Event, key string) string {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(ev.Payload, &m); err != nil {
		t.Fatalf("event %s payload not an object: %v", ev.Type, err)
	}
	s, _ := m[key].(string)
	return s
}

func newScriptedAgent(t *testing.T, script Script, store *EventStore, maxStep int) *Agent {
	t.Helper()
	a, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithTools([]tool.BaseTool{echoTool(t)}),
		WithStore(store),
		WithMaxStep(maxStep),
		WithPersona("测试人格"),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return a
}

func TestRunToolCallRoundTrip(t *testing.T) {
	store := NewEventStore(t.TempDir())
	a := newScriptedAgent(t, roundTripScript(), store, 10)

	ch, err := a.Run(context.Background(), "sess-rt", "开始")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	wantTypes := []string{
		EventTurnStart,
		EventStepStart,        // model step 1
		EventAssistantMessage, // tool_calls message
		EventToolCall,         // echo(call-1)
		EventStepStart,        // tool step 2
		EventToolResult,       // echo -> "hello"
		EventStepStart,        // model step 3
		EventAssistantChunk,   // 流式分片 "done"
		EventAssistantMessage, // final "done"
		EventTurnEnd,
	}
	got := eventTypes(evs)
	if len(got) != len(wantTypes) {
		t.Fatalf("event types = %v, want %v", got, wantTypes)
	}
	for i := range wantTypes {
		if got[i] != wantTypes[i] {
			t.Fatalf("event types = %v, want %v", got, wantTypes)
		}
		if evs[i].Turn != 1 {
			t.Errorf("event %d turn = %d, want 1", i, evs[i].Turn)
		}
	}

	if s := payloadString(t, evs[0], "user"); s != "开始" {
		t.Errorf("turn/start user = %q", s)
	}
	if s := payloadString(t, evs[5], "content"); s != "hello" {
		t.Errorf("tool/result content = %q, want hello", s)
	}
	if s := payloadString(t, evs[8], "content"); s != "done" {
		t.Errorf("final assistant/message content = %q, want done", s)
	}
	if s := payloadString(t, evs[9], "message"); s != "done" {
		t.Errorf("turn/end message = %q, want done", s)
	}

	loaded, err := store.Load("sess-rt")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if len(loaded) != len(evs) {
		t.Fatalf("logged %d events, emitted %d", len(loaded), len(evs))
	}
	for i := range loaded {
		if loaded[i].Type != evs[i].Type {
			t.Errorf("logged event %d type = %s, want %s", i, loaded[i].Type, evs[i].Type)
		}
	}
}

func TestRunDeterministicSameScript(t *testing.T) {
	runOnce := func(t *testing.T, session string) []Event {
		a := newScriptedAgent(t, roundTripScript(), NewEventStore(t.TempDir()), 10)
		ch, err := a.Run(context.Background(), session, "开始")
		if err != nil {
			t.Fatalf("Run: %v", err)
		}
		return collect(t, ch)
	}
	first := runOnce(t, "sess-a")
	second := runOnce(t, "sess-b")
	if len(first) != len(second) {
		t.Fatalf("event count differs: %d vs %d", len(first), len(second))
	}
	for i := range first {
		a, b := first[i], second[i]
		if a.Type != b.Type || a.Turn != b.Turn || a.Step != b.Step ||
			string(a.Payload) != string(b.Payload) {
			t.Errorf("event %d differs:\n a=%s %s\n b=%s %s", i, a.Type, a.Payload, b.Type, b.Payload)
		}
	}
}

func TestRunMaxStepTruncation(t *testing.T) {
	loop := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "call-1", Name: "echo", Arguments: `{"text":"x"}`}}, Repeat: true},
	}}
	a := newScriptedAgent(t, loop, NewEventStore(t.TempDir()), 3)

	ch, err := a.Run(context.Background(), "sess-max", "loop")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	types := eventTypes(evs)
	if types[0] != EventTurnStart || types[len(types)-1] != EventTurnEnd {
		t.Fatalf("events must be bracketed by turn/start..turn/end, got %v", types)
	}
	var errCount, resultCount int
	for _, ev := range evs {
		switch ev.Type {
		case EventError:
			errCount++
			if msg := payloadString(t, ev, "error"); !strings.Contains(msg, "step") {
				t.Errorf("error payload = %q, want mention of step limit", msg)
			}
		case EventToolResult:
			resultCount++
		}
	}
	if errCount == 0 {
		t.Errorf("no error event emitted, want max-step error; types=%v", types)
	}
	if resultCount > 3 {
		t.Errorf("tool executed %d times with MaxStep=3, want <=3", resultCount)
	}
}

// TestRunEmitsAssistantChunks：Stream 路径——文本分片以 assistant/chunk 事件流出，
// 供 chat 层翻译为 message.part.delta；turn/end 携带拼接后的完整答复。
func TestRunEmitsAssistantChunks(t *testing.T) {
	a := newScriptedAgent(t, Script{Steps: []ScriptStep{
		{Chunks: []string{"你好", "，世界"}},
	}}, NewEventStore(t.TempDir()), 10)
	ch, err := a.Run(context.Background(), "sess-chunks", "打招呼")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	var deltas []string
	for _, ev := range evs {
		if ev.Type == EventAssistantChunk {
			deltas = append(deltas, payloadString(t, ev, "content"))
		}
	}
	if len(deltas) != 2 || deltas[0] != "你好" || deltas[1] != "，世界" {
		t.Fatalf("chunk deltas = %v, want [你好 ，世界]", deltas)
	}
	last := evs[len(evs)-1]
	if last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end", last.Type)
	}
	if msg := payloadString(t, last, "message"); msg != "你好，世界" {
		t.Fatalf("turn/end message = %q, want 拼接后的完整答复", msg)
	}
}

// TestRunAppendFailureEmitsErrorEvent：事件日志写盘失败不得静默——
// 失败必须作为 error 事件浮出水面（通道上可见），且不中断后续事件流。
func TestRunAppendFailureEmitsErrorEvent(t *testing.T) {
	dir := t.TempDir()
	// chat/ 目录只读 → Load（文件不存在）正常返回空，Append 写文件必失败
	if err := os.Mkdir(filepath.Join(dir, "chat"), 0o555); err != nil {
		t.Fatal(err)
	}
	a := newScriptedAgent(t, Script{Steps: []ScriptStep{{Chunks: []string{"x"}}}},
		NewEventStore(dir), 10)
	ch, err := a.Run(context.Background(), "sess-storefail", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	var sawStoreErr bool
	for _, ev := range evs {
		if ev.Type != EventError {
			continue
		}
		if msg := payloadString(t, ev, "error"); strings.Contains(msg, "event store") {
			sawStoreErr = true
		}
	}
	if !sawStoreErr {
		t.Fatalf("Append 失败未浮出 error 事件; types=%v", eventTypes(evs))
	}
	// 流程不被写盘失败打断：turn/end 仍收尾
	if evs[len(evs)-1].Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end（写盘失败不应中断循环）", evs[len(evs)-1].Type)
	}
}

// TestRunCancelledNoErrorEvent：主动中止（abort 路径）是正常控制流——
// ctx 取消只收尾 turn/end，不再刷一条 context canceled 的 error 事件污染聊天窗。
func TestRunCancelledNoErrorEvent(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	a := newScriptedAgent(t, Script{Steps: []ScriptStep{{Chunks: []string{"x"}}}},
		NewEventStore(t.TempDir()), 10)
	ch, err := a.Run(ctx, "sess-cancel", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	cancel()
	var evs []Event
	for ev := range ch {
		evs = append(evs, ev)
	}
	for _, ev := range evs {
		if ev.Type == EventError {
			t.Fatalf("取消不应产生 error 事件: %s %s", ev.Type, ev.Payload)
		}
	}
	if len(evs) == 0 || evs[len(evs)-1].Type != EventTurnEnd {
		t.Fatalf("取消后仍应 turn/end 收尾: %v", eventTypes(evs))
	}
}

func TestNewFallsBackToScriptedWhenNoAPIKey(t *testing.T) {
	a, err := New(LLMConfig{}, WithStore(NewEventStore(t.TempDir())))
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := a.Run(context.Background(), "sess-default", "ping")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	types := eventTypes(evs)
	if types[0] != EventTurnStart || types[len(types)-1] != EventTurnEnd {
		t.Fatalf("events = %v, want turn/start..turn/end", types)
	}
	var sawAssistant bool
	for _, ev := range evs {
		if ev.Type == EventAssistantMessage {
			sawAssistant = true
			if payloadString(t, ev, "content") == "" {
				t.Errorf("default scripted answer is empty")
			}
		}
	}
	if !sawAssistant {
		t.Errorf("no assistant/message event; types=%v", types)
	}
}

func TestProjectionFromRunLog(t *testing.T) {
	store := NewEventStore(t.TempDir())
	a := newScriptedAgent(t, roundTripScript(), store, 10)

	ch, err := a.Run(context.Background(), "sess-proj", "问题")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	collect(t, ch)

	loaded, err := store.Load("sess-proj")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	msgs := Project(loaded)
	if len(msgs) != 4 {
		t.Fatalf("projected %d messages, want 4 (user/assistant/tool/assistant): %v", len(msgs), msgs)
	}
	if msgs[0]["role"] != "user" || msgs[0]["content"] != "问题" {
		t.Errorf("msg0 = %v", msgs[0])
	}
	if msgs[1]["role"] != "assistant" {
		t.Errorf("msg1 = %v", msgs[1])
	}
	if msgs[2]["role"] != "tool" || msgs[2]["content"] != "hello" {
		t.Errorf("msg2 = %v", msgs[2])
	}
	if msgs[3]["role"] != "assistant" || msgs[3]["content"] != "done" {
		t.Errorf("msg3 = %v", msgs[3])
	}
}

func TestRunTurnNumberIncrements(t *testing.T) {
	store := NewEventStore(t.TempDir())
	a := newScriptedAgent(t, Script{Steps: []ScriptStep{{Chunks: []string{"a1"}}}}, store, 10)

	for want := 1; want <= 2; want++ {
		ch, err := a.Run(context.Background(), "sess-turns", "q")
		if err != nil {
			t.Fatalf("Run %d: %v", want, err)
		}
		evs := collect(t, ch)
		for _, ev := range evs {
			if ev.Turn != want {
				t.Fatalf("run %d produced event with Turn=%d", want, ev.Turn)
			}
		}
	}
}
