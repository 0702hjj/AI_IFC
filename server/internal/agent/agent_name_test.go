package agent

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/cloudwego/eino/components/tool"
)

// TestRunModelStepNameCarriesAgentName：模型 step/start 的 name 反映 Agent 名
// （默认 aiifc-main；WithName 覆盖——子 agent 经 runChild 传 persona 名，
// 前端 step/start 展示可区分主/子角色）。
func TestRunModelStepNameCarriesAgentName(t *testing.T) {
	cases := []struct {
		name string
		want string
	}{
		{"", "aiifc-main"},         // 默认
		{"cad-agent", "cad-agent"}, // WithName 覆盖（runChild 传 PersonaCAD）
	}
	for _, c := range cases {
		opts := []Option{
			WithModel(NewScriptedModel(Script{Steps: []ScriptStep{{Chunks: []string{"x"}}}})),
			WithTools([]tool.BaseTool{echoTool(t)}),
			WithMaxStep(10),
		}
		if c.name != "" {
			opts = append(opts, WithName(c.name))
		}
		a, err := New(LLMConfig{}, opts...)
		if err != nil {
			t.Fatalf("New(%s): %v", c.name, err)
		}
		ch, err := a.Run(context.Background(), "sess-name", "hi")
		if err != nil {
			t.Fatalf("Run(%s): %v", c.name, err)
		}
		evs := collect(t, ch)

		var got string
		found := false
		for _, ev := range evs {
			if ev.Type != EventStepStart {
				continue
			}
			var p map[string]any
			if err := json.Unmarshal(ev.Payload, &p); err != nil {
				t.Fatalf("step/start payload: %v", err)
			}
			if p["kind"] == "model" {
				got, _ = p["name"].(string)
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("未找到 model step/start 事件；types=%v", eventTypes(evs))
		}
		if got != c.want {
			t.Errorf("model step/start name = %q, want %q", got, c.want)
		}
	}
}
