package agent

import (
	"context"
	"os"
	"strings"
	"testing"
)

// TestExecuteRunsSkillCLI：第二层集成——独立 skill venv 的 bin 注入 PATH 后，
// execute 能真跑 skill CLI（aiplan gate --help / aidxfv3 --help）。前置：跑过
// tools/install_skill_venv.sh（venv 存在才执行，否则 skip）。
func TestExecuteRunsSkillCLI(t *testing.T) {
	venvBin := "/home/cyvol0521/.code/gaiahub/CADapi/AI_IFC/skills/.venv/bin"
	if _, err := os.Stat(venvBin + "/aiplan"); err != nil {
		t.Skipf("skill venv 未安装（先跑 tools/install_skill_venv.sh）: %v", err)
	}
	t.Setenv("PATH", venvBin+string(os.PathListSeparator)+os.Getenv("PATH"))

	script := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "e1", Name: "execute", Arguments: `{"command":"aiplan gate --help"}`}}},
		{ToolCalls: []ToolCallSpec{{ID: "e2", Name: "execute", Arguments: `{"command":"aidxfv3 --help"}`}}},
		{Chunks: []string{"CLI 执行完成"}},
	}}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(script)),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-cli", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	var results []string
	for _, ev := range evs {
		if ev.Type != EventToolResult || payloadString(t, ev, "name") != "execute" {
			continue
		}
		results = append(results, payloadString(t, ev, "content"))
	}
	if len(results) != 2 {
		t.Fatalf("execute 结果数 = %d, want 2；types=%v", len(results), eventTypes(evs))
	}
	if !strings.Contains(results[0], "usage") && !strings.Contains(results[0], "gate") {
		t.Errorf("aiplan gate --help 输出异常: %s...", truncate(results[0], 120))
	}
	if !strings.Contains(results[1], "usage") && !strings.Contains(results[1], "preprocess") {
		t.Errorf("aidxfv3 --help 输出异常: %s...", truncate(results[1], 120))
	}
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd {
		t.Fatalf("末事件 = %s, want turn/end", last.Type)
	}
}
