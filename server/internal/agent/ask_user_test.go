package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/cloudwego/eino/adk"
)

// TestTranslatorOnInterruptEmitsQuestion：翻译层单测——Interrupted 中断
// 提取 root cause 的 AskUserInfo → 发 question/ask 帧（interruptId/question/checkpointId）。
func TestTranslatorOnInterruptEmitsQuestion(t *testing.T) {
	var got Event
	tr := newAdkTranslator(1, "main", "sess-q", 10, func(ev Event) { got = ev })
	tr.onInterrupt(&adk.InterruptInfo{InterruptContexts: []*adk.InterruptCtx{
		{ID: "agent:main;tool:ask_user", Info: &AskUserInfo{Question: "确认层高 3 米？"}, IsRootCause: true},
	}})

	if got.Type != EventQuestionAsk {
		t.Fatalf("中断应发 question/ask，got %s", got.Type)
	}
	if payloadString(t, got, "question") != "确认层高 3 米？" {
		t.Fatalf("question = %q", payloadString(t, got, "question"))
	}
	if payloadString(t, got, "interruptId") != "agent:main;tool:ask_user" {
		t.Fatalf("interruptId = %q", payloadString(t, got, "interruptId"))
	}
	if payloadString(t, got, "checkpointId") != "sess-q" {
		t.Fatalf("checkpointId = %q", payloadString(t, got, "checkpointId"))
	}
}

// TestAskUserEndToEnd：HITL 端到端——
// ① Run：模型调 ask_user → 中断 → 翻译层发 question/ask 帧（流关闭，无 turn/end）
// ② Resume：用户回答（interruptID → AskUserInfo.UserAnswer）→ 续跑 → 工具返回回答 → turn/end
func TestAskUserEndToEnd(t *testing.T) {
	store := NewEventStore(t.TempDir())
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "a1", Name: "ask_user", Arguments: `{"question":"确认层高 3 米？"}`}}},
		{Chunks: []string{"已确认，继续执行"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithStore(store),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	// ① Run → 中断
	ch, err := ag.Run(context.Background(), "sess-ask", "帮我建墙")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	var interruptID string
	var qEvent Event
	for _, ev := range evs {
		if ev.Type == EventQuestionAsk {
			qEvent = ev
			interruptID = payloadString(t, ev, "interruptId")
		}
		if ev.Type == EventTurnEnd {
			t.Fatalf("中断后不应有 turn/end（等 Resume 续跑）：%v", ev)
		}
	}
	if interruptID == "" {
		t.Fatalf("未收到 question/ask；types=%v", eventTypes(evs))
	}
	if payloadString(t, qEvent, "question") != "确认层高 3 米？" {
		t.Fatalf("question = %q", payloadString(t, qEvent, "question"))
	}

	// ② Resume：用户回答
	ch2, err := ag.Resume(context.Background(), "sess-ask", &adk.ResumeParams{
		Targets: map[string]any{
			interruptID: &AskUserInfo{Question: "确认层高 3 米？", UserAnswer: "确认"},
		},
	})
	if err != nil {
		t.Fatalf("Resume: %v", err)
	}
	evs2 := collect(t, ch2)

	// 续跑后：ask_user 工具返回用户回答（"确认"），最终 turn/end
	var sawAnswer bool
	for _, ev := range evs2 {
		if ev.Type == EventToolResult && payloadString(t, ev, "name") == "ask_user" {
			if c := payloadString(t, ev, "content"); strings.Contains(c, "确认") {
				sawAnswer = true
			}
		}
	}
	if !sawAnswer {
		t.Fatalf("Resume 后 ask_user 应返回用户回答；types=%v", eventTypes(evs2))
	}
	if last := evs2[len(evs2)-1]; last.Type != EventTurnEnd {
		t.Fatalf("Resume 后应 turn/end 收尾，got %s", last.Type)
	}
}

// TestAskUserStatePreservedOnNonTargetResume：非目标中断时重新挂起（保留原问题）。
func TestAskUserStatePreservedOnNonTargetResume(t *testing.T) {
	store := NewEventStore(t.TempDir())
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "a1", Name: "ask_user", Arguments: `{"question":"方案 A 还是 B？"}`}}},
		{Chunks: []string{"收尾"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithStore(store),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-state", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	var interruptID string
	for _, ev := range evs {
		if ev.Type == EventQuestionAsk {
			interruptID = payloadString(t, ev, "interruptId")
		}
	}
	if interruptID == "" {
		t.Fatalf("未收到 question/ask；types=%v", eventTypes(evs))
	}
	// 用错误的目标 ID resume（模拟其他断点被回答）→ 当前 ask_user 非目标 → 重新中断
	ch2, err := ag.Resume(context.Background(), "sess-state", &adk.ResumeParams{
		Targets: map[string]any{
			"other-interrupt": &AskUserInfo{UserAnswer: "x"},
		},
	})
	if err != nil {
		t.Fatalf("Resume: %v", err)
	}
	evs2 := collect(t, ch2)
	// 重新中断 → 又收到 question/ask（原问题保留）
	var requestion bool
	for _, ev := range evs2 {
		if ev.Type == EventQuestionAsk && payloadString(t, ev, "question") == "方案 A 还是 B？" {
			requestion = true
		}
	}
	if !requestion {
		t.Fatalf("非目标 resume 应重新挂起原问题；types=%v", eventTypes(evs2))
	}
}
