package agent

import (
	"context"
	"strings"
	"testing"
)

// TestSkeletonRealSkillsIntegration：真实仓库 skills/dist 目录 + scriptedModel 的
// 端到端骨架验证——orchestrator 角色化挂 aiplan，调用返回真实 aiplan SKILL.md 正文
// （progressive disclosure 内容片段）。验证「接入 ADK skill」在真实数据上闭环。
func TestSkeletonRealSkillsIntegration(t *testing.T) {
	ag, err := New(LLMConfig{},
		WithSkillsDir(distSkillsDir()),
		WithModel(NewScriptedModel(Script{Steps: []ScriptStep{
			{ToolCalls: []ToolCallSpec{{ID: "s1", Name: "skill", Arguments: `{"skill":"aiplan"}`}}},
			{Chunks: []string{"已加载 aiplan skill"}},
		}})),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-real-skill", "加载 aiplan")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	var content string
	found := false
	for _, ev := range evs {
		if ev.Type != EventToolResult {
			continue
		}
		if payloadString(t, ev, "name") != "skill" {
			continue
		}
		found = true
		content = payloadString(t, ev, "content")
	}
	if !found {
		t.Fatalf("未观测到 skill 工具结果；types=%v", eventTypes(evs))
	}
	// 真实 aiplan SKILL.md 的关键片段（官方 defaultSkillContent 组装：
	// "Launching skill: <name>" + BaseDirectory + SKILL.md 正文）
	for _, want := range []string{"Launching skill: aiplan", "plan 阶段 skill", "资深建筑方案设计师"} {
		if !strings.Contains(content, want) {
			t.Errorf("skill 结果缺 %q 片段；content=%s...", want, truncate(content, 120))
		}
	}
	if !strings.Contains(content, "/skills/dist/aiplan") {
		t.Errorf("skill 结果缺 BaseDirectory 路径（/skills/dist/aiplan）")
	}
	// 整轮正常收尾
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end", last.Type)
	}
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n]) + "..."
}
