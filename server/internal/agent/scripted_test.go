package agent

import (
	"context"
	"testing"

	"github.com/cloudwego/eino/schema"
)

func twoStepScript() Script {
	return Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "call-1", Name: "echo", Arguments: `{"text":"hi"}`}}},
		{Chunks: []string{"最终", "答复"}},
	}}
}

func TestScriptedModelGenerateSteps(t *testing.T) {
	m := NewScriptedModel(twoStepScript())
	ctx := context.Background()

	first, err := m.Generate(ctx, []*schema.Message{schema.UserMessage("go")})
	if err != nil {
		t.Fatalf("Generate step1: %v", err)
	}
	if first.Role != schema.Assistant {
		t.Errorf("step1 role = %v", first.Role)
	}
	if len(first.ToolCalls) != 1 {
		t.Fatalf("step1 tool calls = %d, want 1", len(first.ToolCalls))
	}
	tc := first.ToolCalls[0]
	if tc.ID != "call-1" || tc.Function.Name != "echo" || tc.Function.Arguments != `{"text":"hi"}` {
		t.Errorf("step1 tool call = %+v", tc)
	}

	second, err := m.Generate(ctx, []*schema.Message{
		schema.UserMessage("go"), first,
		schema.ToolMessage("hi", "call-1"),
	})
	if err != nil {
		t.Fatalf("Generate step2: %v", err)
	}
	if second.Content != "最终答复" {
		t.Errorf("step2 content = %q, want 最终答复", second.Content)
	}
	if len(second.ToolCalls) != 0 {
		t.Errorf("step2 tool calls = %d, want 0", len(second.ToolCalls))
	}
}

func TestScriptedModelStreamChunks(t *testing.T) {
	m := NewScriptedModel(twoStepScript())
	ctx := context.Background()

	if _, err := m.Generate(ctx, []*schema.Message{schema.UserMessage("go")}); err != nil {
		t.Fatalf("Generate step1: %v", err)
	}
	sr, err := m.Stream(ctx, []*schema.Message{schema.UserMessage("go")})
	if err != nil {
		t.Fatalf("Stream: %v", err)
	}
	defer sr.Close()

	var frames []*schema.Message
	for {
		frame, err := sr.Recv()
		if err != nil {
			break
		}
		frames = append(frames, frame)
	}
	if len(frames) != 2 {
		t.Fatalf("stream frames = %d, want 2", len(frames))
	}
	if frames[0].Content != "最终" || frames[1].Content != "答复" {
		t.Errorf("frames content = %q,%q", frames[0].Content, frames[1].Content)
	}
}

func TestScriptedModelRepeatLastStep(t *testing.T) {
	m := NewScriptedModel(Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "call-1", Name: "echo", Arguments: `{}`}}, Repeat: true},
	}})
	ctx := context.Background()
	for i := 0; i < 5; i++ {
		msg, err := m.Generate(ctx, nil)
		if err != nil {
			t.Fatalf("Generate round %d: %v", i, err)
		}
		if len(msg.ToolCalls) != 1 {
			t.Fatalf("round %d tool calls = %d, want 1 (repeat)", i, len(msg.ToolCalls))
		}
	}
}

func TestScriptedModelExhaustedYieldsEmptyFinal(t *testing.T) {
	m := NewScriptedModel(Script{Steps: []ScriptStep{{Chunks: []string{"only"}}}})
	ctx := context.Background()
	if _, err := m.Generate(ctx, nil); err != nil {
		t.Fatalf("Generate: %v", err)
	}
	msg, err := m.Generate(ctx, nil)
	if err != nil {
		t.Fatalf("Generate past end: %v", err)
	}
	if msg.Content != "" || len(msg.ToolCalls) != 0 {
		t.Errorf("past-end message = %+v, want empty assistant message", msg)
	}
}

func TestScriptedModelWithToolsCopies(t *testing.T) {
	m := NewScriptedModel(twoStepScript())
	tools := []*schema.ToolInfo{{Name: "echo"}}
	m2, err := m.WithTools(tools)
	if err != nil {
		t.Fatalf("WithTools: %v", err)
	}
	if m2 == m {
		t.Errorf("WithTools returned same instance, want copy")
	}
	if _, err := m2.Generate(context.Background(), nil); err != nil {
		t.Fatalf("Generate on bound model: %v", err)
	}
}
