package agent

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/tool"
)

// mkFakeSkillDir 构造扁平 skills 目录（BaseDir/*/SKILL.md，frontmatter 含 name）。
func mkFakeSkillDir(t *testing.T, name, body string) string {
	t.Helper()
	dir := t.TempDir()
	skillDir := filepath.Join(dir, name)
	if err := os.MkdirAll(skillDir, 0o755); err != nil {
		t.Fatal(err)
	}
	content := "---\nname: " + name + "\ndescription: 测试 skill\n---\n\n" + body
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

// TestSkillMiddlewareInjectsSkillTool：挂 WithSkillsDir 后，模型工具面出现官方
// skill 工具（名为 skill）；scriptedModel 调用它 → tool/result 返回 SKILL.md 正文
// + BaseDirectory。这是「接入 ADK skill」的最小闭环（ch09 装配路径）。
// 注：orchestrator 角色化只允许 aiplan（第一层角色映射），假 skill 名必须匹配。
func TestSkillMiddlewareInjectsSkillTool(t *testing.T) {
	skillDir := mkFakeSkillDir(t, "aiplan", "# 测试 skill\n\n参考文件在 references/ 下。")

	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "s1", Name: "skill", Arguments: `{"skill":"aiplan"}`}}},
		{Chunks: []string{"已加载"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithSkillsDir(skillDir),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ch, err := ag.Run(context.Background(), "sess-skill", "加载 skill")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	var sawSkillResult bool
	for _, ev := range evs {
		if ev.Type != EventToolResult {
			continue
		}
		if payloadString(t, ev, "name") != "skill" {
			continue
		}
		sawSkillResult = true
		content := payloadString(t, ev, "content")
		if !strings.Contains(content, "# 测试 skill") {
			t.Fatalf("skill 工具结果不含 SKILL.md 正文: %q", content)
		}
		if !strings.Contains(content, "references/") {
			t.Fatalf("skill 工具结果不含 BaseDirectory 提示: %q", content)
		}
	}
	if !sawSkillResult {
		t.Fatalf("未观测到 skill 工具的 tool/result；类型序列=%v", eventTypes(evs))
	}
	// 整轮正常收尾
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end", last.Type)
	}
}

// TestSkillMiddlewareWithoutDirNoSkillTool：不传 WithSkillsDir（默认路径），
// 模型工具面没有 skill 工具——离线/测试路径不受影响。
func TestSkillMiddlewareWithoutDirNoSkillTool(t *testing.T) {
	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "e1", Name: "echo", Arguments: `{"text":"hi"}`}}},
		{Chunks: []string{"done"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithTools([]tool.BaseTool{echoTool(t)}),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-noskill", "hi")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	for _, ev := range collect(t, ch) {
		if ev.Type == EventToolCall && payloadString(t, ev, "name") == "skill" {
			t.Fatalf("未配置 skillsDir 却出现 skill 工具调用")
		}
	}
}
