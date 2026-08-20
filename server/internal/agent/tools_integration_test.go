// tools_integration_test.go：agent 集成面——ctx 会话注入工具、工具 Go error
// 的单卡映射（error 载荷 tool/result 事件，不再刷 session 级 error）。
package agent

import (
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/tool"
)

// --- agent 集成：工具错误的单卡映射 + ctx 会话注入 ---

func TestRunInjectsSessionIDToToolCtx(t *testing.T) {
	var gotSid string
	sidTool, err := newStringTool("whoami", func(ctx context.Context) (string, error) {
		gotSid = SessionIDFromContext(ctx)
		return "ok", nil
	})
	if err != nil {
		t.Fatal(err)
	}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(Script{Steps: []ScriptStep{
			{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "whoami", Arguments: `{}`}}},
			{Chunks: []string{"done"}},
		}})),
		WithTools([]tool.BaseTool{sidTool}),
	)
	if err != nil {
		t.Fatal(err)
	}
	events, err := ag.Run(context.Background(), "s_ctxinjection", "hi")
	if err != nil {
		t.Fatal(err)
	}
	collect(t, events)
	if gotSid != "s_ctxinjection" {
		t.Fatalf("工具 ctx 会话 id = %q, want s_ctxinjection", gotSid)
	}
}

// TestToolErrorEmitsErrorToolResult：工具返回 Go error（框架级失败）时，
// 事件流应给出带 error 载荷的 tool/result（前端渲染单卡错误态），
// 而非只有 session.error 横幅；lastErr 去重保证不重复上报。
func TestToolErrorEmitsErrorToolResult(t *testing.T) {
	boomTool, err := newStringTool("boom", func(ctx context.Context) (string, error) {
		return "", errors.New("kaboom")
	})
	if err != nil {
		t.Fatal(err)
	}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(Script{Steps: []ScriptStep{
			{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "boom", Arguments: `{}`}}},
		}})),
		WithTools([]tool.BaseTool{boomTool}),
	)
	if err != nil {
		t.Fatal(err)
	}
	events, err := ag.Run(context.Background(), "s_toolerror", "hi")
	if err != nil {
		t.Fatal(err)
	}
	evs := collect(t, events)
	var errResult, errEvent, turnEnd bool
	for _, ev := range evs {
		switch ev.Type {
		case EventToolResult:
			// eino 会包裹工具错误（[LocalFunc] failed to invoke tool … err=kaboom），
			// 断言含原始错误文本即可（LLM/前端可观测）。
			if e := payloadString(t, ev, "error"); strings.Contains(e, "kaboom") {
				errResult = true
			}
		case EventError:
			errEvent = true
		case EventTurnEnd:
			turnEnd = true
		}
	}
	if !errResult {
		t.Fatalf("缺带 error 载荷的 tool/result 事件: %v", eventTypes(evs))
	}
	if errEvent {
		t.Fatalf("工具错误不应再刷 session 级 error 事件（单卡映射替代）: %v", eventTypes(evs))
	}
	if !turnEnd {
		t.Fatalf("缺 turn/end 收尾: %v", eventTypes(evs))
	}
}
