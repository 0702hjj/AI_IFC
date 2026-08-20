package agent

import (
	"context"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
)

// TestRoleSkillBoundaryOrchestrator：第一层角色映射——orchestrator 只允许 aiplan
// （对话协调层内联）；调 aiifc 被角色过滤拒绝（文本错误，不中断循环）。
func TestRoleSkillBoundaryOrchestrator(t *testing.T) {
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "s1", Name: "skill", Arguments: `{"skill":"aiifc"}`}}},
		{Chunks: []string{"收尾"}},
	}}
	ag, err := New(LLMConfig{},
		WithSkillsDir(distSkillsDir()),
		WithModel(NewScriptedModel(script)),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-role", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	var errText string
	for _, ev := range evs {
		if ev.Type == EventToolResult && payloadString(t, ev, "name") == "skill" {
			errText = payloadString(t, ev, "error")
			if errText == "" {
				errText = payloadString(t, ev, "content")
			}
		}
	}
	if !strings.Contains(errText, "不属于当前角色") || !strings.Contains(errText, "aiplan") {
		t.Fatalf("orchestrator 调 aiifc 应被角色过滤拒绝：%q", errText)
	}
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end（拒绝不中断循环）", last.Type)
	}
}

// TestRoleSkillBoundarySubAgent：第一层角色映射——ifc-agent 子 agent 只允许 aiifc；
// 派发后子 agent 调 skill{"skill":"aiifc"} 成功（返回 SKILL.md），调 aiplan 被拒。
func TestRoleSkillBoundarySubAgent(t *testing.T) {
	// 子脚本：先调 skill aiifc（允许），再调 skill aiplan（拒绝），收尾
	child := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "skill", Arguments: `{"skill":"aiifc"}`}}},
		{ToolCalls: []ToolCallSpec{{ID: "c2", Name: "skill", Arguments: `{"skill":"aiplan"}`}}},
		{Chunks: []string{"子完成"}},
	}}
	parent := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"改个墙"}`}}},
		{Chunks: []string{"汇总"}},
	}}
	ag, err := New(LLMConfig{},
		WithSkillsDir(distSkillsDir()),
		WithModel(NewScriptedModel(parent)),
		WithChildModelFactory(func() model.ToolCallingChatModel { return NewScriptedModel(child) }),
		WithTools([]tool.BaseTool{echoTool(t)}),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-child-role", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	// 子窗口内：第一个 skill 调用成功（aiifc），第二个被拒（aiplan）
	var results []string
	for _, ev := range evs {
		if ev.Type != EventToolResult || payloadString(t, ev, "name") != "skill" {
			continue
		}
		r := payloadString(t, ev, "content")
		if r == "" {
			r = payloadString(t, ev, "error")
		}
		results = append(results, r)
	}
	if len(results) != 2 {
		t.Fatalf("子 skill 调用结果数 = %d, want 2；types=%v", len(results), eventTypes(evs))
	}
	if !strings.Contains(results[0], "Launching skill: aiifc") {
		t.Errorf("ifc-agent 调 aiifc 应成功，got %q", results[0])
	}
	if !strings.Contains(results[1], "不属于当前角色") || !strings.Contains(results[1], "aiifc") {
		t.Errorf("ifc-agent 调 aiplan 应被拒（仅允许 aiifc），got %q", results[1])
	}
}
