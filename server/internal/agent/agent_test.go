package agent

import (
	"context"
	"encoding/json"
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
		EventStepStart,         // model step 1
		EventAssistantMessage,  // tool_calls message
		EventToolCall,          // echo(call-1)
		EventStepStart,         // tool step 2
		EventToolResult,        // echo -> "hello"
		EventStepStart,         // model step 3
		EventAssistantMessage,  // final "done"
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
	if s := payloadString(t, evs[7], "content"); s != "done" {
		t.Errorf("final assistant/message content = %q, want done", s)
	}
	if s := payloadString(t, evs[8], "message"); s != "done" {
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
