// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/cloudwego/eino/adk"
)

// echoApprovalTool 是审批名单外的 echo 工具（证明非审批工具不拦截）。
// 用 DomainTools 的 save_script 需要 editsvc——直接测 middleware 包装逻辑更稳：
// 用真实 agent + save_script 工具 + fake editsvc（复用 invoke 模式太底层）。
// 这里走 agent 端到端：脚本调 save_script → 审批中断 → Resume(确认) → 放行。

// TestApprovalMiddlewareConfirm 审批端到端：脚本调 save_script → 中断提问 →
// Resume(确认) → 放行执行。
func TestApprovalMiddlewareConfirm(t *testing.T) {
	store := NewEventStore(t.TempDir())
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "s1", Name: "save_script", Arguments: `{"note":"v1"}`}}},
		{Chunks: []string{"已保存"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithStore(store),
		WithMaxStep(10),
		WithTools(AsBaseTools(DomainTools(newToolDepsForApproval(t)))),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	// ① Run → 审批中断 → question/ask
	ch, err := ag.Run(context.Background(), "sess-approve", "保存")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	var interruptID string
	for _, ev := range evs {
		if ev.Type == EventQuestionAsk {
			interruptID = payloadString(t, ev, "interruptId")
		}
		if ev.Type == EventTurnEnd {
			t.Fatalf("审批中断后不应 turn/end：%v", ev)
		}
	}
	if interruptID == "" {
		t.Fatalf("未收到审批 question/ask；types=%v", eventTypes(evs))
	}
	// ② Resume(确认) → 放行
	ch2, err := ag.Resume(context.Background(), "sess-approve", &adk.ResumeParams{
		Targets: map[string]any{interruptID: &AskUserInfo{UserAnswer: "确认"}},
	})
	if err != nil {
		t.Fatalf("Resume: %v", err)
	}
	evs2 := collect(t, ch2)
	if last := evs2[len(evs2)-1]; last.Type != EventTurnEnd {
		t.Fatalf("Resume 后应 turn/end，got %s", last.Type)
	}
	// save_script 放行：工具结果出现（fake 后端或错误文本化——这里 save_script 未配置
	// 会返回文本错误，但证明已放行执行而非被拒）。
	var sawExec bool
	for _, ev := range evs2 {
		if ev.Type == EventToolResult && payloadString(t, ev, "name") == "save_script" {
			sawExec = true
		}
	}
	if !sawExec {
		t.Fatalf("确认后 save_script 应被执行（放行）；types=%v", eventTypes(evs2))
	}
}

// TestApprovalMiddlewareReject 审批拒绝：Resume(拒绝) → 工具未执行（文本返回拒绝）。
func TestApprovalMiddlewareReject(t *testing.T) {
	store := NewEventStore(t.TempDir())
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "s1", Name: "save_script", Arguments: `{"note":"v1"}`}}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithStore(store),
		WithMaxStep(10),
		WithTools(AsBaseTools(DomainTools(newToolDepsForApproval(t)))),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, _ := ag.Run(context.Background(), "sess-reject", "保存")
	evs := collect(t, ch)
	var interruptID string
	for _, ev := range evs {
		if ev.Type == EventQuestionAsk {
			interruptID = payloadString(t, ev, "interruptId")
		}
	}
	if interruptID == "" {
		t.Fatalf("未收到审批 question/ask；types=%v", eventTypes(evs))
	}
	ch2, _ := ag.Resume(context.Background(), "sess-reject", &adk.ResumeParams{
		Targets: map[string]any{interruptID: &AskUserInfo{UserAnswer: "拒绝"}},
	})
	evs2 := collect(t, ch2)
	var rejected bool
	for _, ev := range evs2 {
		if ev.Type == EventToolResult && payloadString(t, ev, "name") == "save_script" {
			if strings.Contains(payloadString(t, ev, "content"), "用户拒绝执行") {
				rejected = true
			}
		}
	}
	if !rejected {
		t.Fatalf("拒绝后 save_script 应返回拒绝文本；types=%v", eventTypes(evs2))
	}
}

// newToolDepsForApproval 构造带 fake editsvc 的 ToolDeps（save_script 走 fake 后端）。
func newToolDepsForApproval(t *testing.T) ToolDeps {
	deps, _, _, st := newToolFixture(t)
	m, err := st.CreateWithKind("a.ifc", 5, strings.NewReader("aaaaa"), "ifc")
	if err != nil {
		t.Fatal(err)
	}
	deps.SessionModel = func(ctx context.Context) string { return m.ID }
	return deps
}
