// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// subagent_test.go：AgentAsTool（路线 B，D10）契约——
// orchestrator 经官方 adk.NewAgentTool 派发 ifc/cad 子 agent：
//   - 子事件按 RunPath 深度≥2 打 subagentId/parentSessionId 标签上浮（翻译层合成）
//   - subagent/status started/finished 由翻译层在子边界合成
//   - 深度预算 1（子 agent 无 AgentAsTool，结构性）
//   - 子 agent 继承父会话绑定（SessionIDFromContext / kind 路由可用）
//   - 事件日志含标签、父 turn 计数不被子事件污染、Project 跳过子事件
package agent

import (
	"context"
	"encoding/json"
	"strings"
	"testing"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
)

// childScript 一次子 agent run 的标准脚本：先调工具再收尾答复。
func childScript() Script {
	return Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "cc-1", Name: "echo", Arguments: `{"text":"子工具结果"}`}}},
		{Chunks: []string{"子代理完成"}},
	}}
}

// parentScriptWithAgentTool 主 agent 脚本：第一步调子 agent 工具（AgentAsTool，
// 工具名 = 子 agent Name），第二步汇总。
func parentScriptWithAgentTool(calls ...ToolCallSpec) Script {
	return Script{Steps: []ScriptStep{
		{ToolCalls: calls},
		{Chunks: []string{"汇总完成"}},
	}}
}

// newOrchestrator 装配测试用三角色：orchestrator（parentScript）+ ifc/cad 子
// agent（childScript，独立 scripted 实例经工厂产出）。tools 同时是 orchestrator
// 领域工具与子 agent 工具面（当前全量共享，A2 分离留后续）。
func newOrchestrator(t *testing.T, parentScript, childScript Script, tools []tool.BaseTool) *Agent {
	t.Helper()
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScript)),
		WithChildModelFactory(func() model.ToolCallingChatModel { return NewScriptedModel(childScript) }),
		WithTools(tools),
		WithMaxStep(10),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return ag
}

func findStatus(t *testing.T, evs []Event, status string) (idx int, ev Event) {
	t.Helper()
	for i, ev := range evs {
		if ev.Type != EventSubagentStatus {
			continue
		}
		var p map[string]any
		if err := json.Unmarshal(ev.Payload, &p); err != nil {
			t.Fatalf("subagent/status payload: %v", err)
		}
		if s, _ := p["status"].(string); s == status {
			return i, ev
		}
	}
	t.Fatalf("未找到 status=%s 的 subagent/status 事件；类型序列=%v", status, eventTypes(evs))
	return 0, Event{}
}

// TestAgentToolDispatchEndToEnd：orchestrator 调 ifc-agent（AgentAsTool）→
// 子事件按 RunPath 打标上浮 → subagent/status started/finished 合成 →
// 父工具结果 = 子 agent 最终答复。
func TestAgentToolDispatchEndToEnd(t *testing.T) {
	store := NewEventStore(t.TempDir())
	ag := newOrchestrator(t,
		parentScriptWithAgentTool(ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"建一堵墙"}`}),
		childScript(),
		[]tool.BaseTool{echoTool(t)},
	)
	ag.store = store

	ch, err := ag.Run(context.Background(), "sess-sub", "开始")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	iStart, startEv := findStatus(t, evs, "started")
	iFin, finEv := findStatus(t, evs, "finished")
	subID := "sa_1_1"
	if startEv.SubagentID != subID || startEv.ParentSessionID != "sess-sub" {
		t.Fatalf("started 标签 subagentId=%q parentSessionId=%q, want %s/sess-sub",
			startEv.SubagentID, startEv.ParentSessionID, subID)
	}
	if finEv.SubagentID != subID {
		t.Fatalf("finished 标签 subagentId=%q, want %s", finEv.SubagentID, subID)
	}
	if iFin <= iStart {
		t.Fatalf("finished(%d) 应在 started(%d) 之后", iFin, iStart)
	}
	// started 载荷五字段（persona=子 agent 名，task=父 tool_call arguments）
	var sp map[string]any
	if err := json.Unmarshal(startEv.Payload, &sp); err != nil {
		t.Fatal(err)
	}
	if sp["persona"] != PersonaIFC || sp["task"] != `{"request":"建一堵墙"}` || sp["parentSessionId"] != "sess-sub" {
		t.Fatalf("started 载荷 = %v", sp)
	}

	// (started, finished) 窗口内全部事件属于该子 agent（全部打标签）
	var childTypes []string
	for i := iStart + 1; i < iFin; i++ {
		if evs[i].SubagentID != subID || evs[i].ParentSessionID != "sess-sub" {
			t.Fatalf("窗口内事件 %d（%s）标签 = %q/%q, want %s/sess-sub",
				i, evs[i].Type, evs[i].SubagentID, evs[i].ParentSessionID, subID)
		}
		childTypes = append(childTypes, evs[i].Type)
	}
	joined := strings.Join(childTypes, ",")
	for _, want := range []string{EventToolCall, EventToolResult, EventAssistantChunk, EventAssistantMessage} {
		if !strings.Contains(joined, want) {
			t.Fatalf("子事件序列缺 %s: %v", want, childTypes)
		}
	}
	// 窗口外不允许出现该 subID（父事件不被误标）
	for i, ev := range evs {
		if i >= iStart && i <= iFin {
			continue
		}
		if ev.SubagentID == subID {
			t.Fatalf("窗口外事件 %d（%s）误带 subagentId", i, ev.Type)
		}
	}

	// finished 后 = 父 AgentAsTool 工具 step/start + tool/result（内容 = 子最终答复）
	if got := payloadString(t, evs[iFin+1], "name"); got != PersonaIFC || evs[iFin+1].Type != EventStepStart {
		t.Fatalf("finished 后应为 AgentAsTool 的 step/start，得到 %s/%s（序列=%v）", evs[iFin+1].Type, got, eventTypes(evs))
	}
	if evs[iFin+2].Type != EventToolResult {
		t.Fatalf("step/start 后应为 tool/result，得到 %s（序列=%v）", evs[iFin+2].Type, eventTypes(evs))
	}
	if c := payloadString(t, evs[iFin+2], "content"); !strings.Contains(c, "子代理完成") {
		t.Fatalf("AgentAsTool 工具结果 = %q, want 含子 agent 最终答复", c)
	}
	// 主 turn 正常收尾
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd || payloadString(t, last, "message") != "汇总完成" {
		t.Fatalf("主 turn 收尾异常: %s %s", last.Type, last.Payload)
	}
}

// TestAgentToolDepthBudgetStructural：深度预算 1 结构性钉死——
// orchestrator 工具面含 ifc-agent/cad-agent（AgentAsTool）；子 agent 实际 run
// 的 tool/call 名单 ⊆ 领域工具（无 AgentAsTool，孙代派发结构性不可能）。
func TestAgentToolDepthBudgetStructural(t *testing.T) {
	ag := newOrchestrator(t,
		parentScriptWithAgentTool(ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"hi"}`}),
		childScript(),
		[]tool.BaseTool{echoTool(t)},
	)
	ch, err := ag.Run(context.Background(), "sess-depth", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	// 父侧：出现 AgentAsTool 工具调用（ifc-agent）
	var parentAgentTools []string
	// 子窗口内：只调领域工具（echo），不得出现 ifc-agent/cad-agent（孙代派发不可能）
	iStart, _ := findStatus(t, evs, "started")
	iFin, _ := findStatus(t, evs, "finished")
	for i, ev := range evs {
		if ev.Type != EventToolCall {
			continue
		}
		name := payloadString(t, ev, "name")
		if i >= iStart && i <= iFin {
			if name == PersonaIFC || name == PersonaCAD {
				t.Fatalf("子窗口内出现 AgentAsTool 调用 %s（深度预算被突破）", name)
			}
			continue
		}
		if name == PersonaIFC || name == PersonaCAD {
			parentAgentTools = append(parentAgentTools, name)
		}
	}
	if len(parentAgentTools) == 0 {
		t.Fatalf("orchestrator 未调用 AgentAsTool 工具；序列=%v", eventTypes(evs))
	}
}

// TestAgentToolUniqueIDs：同一 turn 连续两次派发（ifc→cad），subagentId 递增。
func TestAgentToolUniqueIDs(t *testing.T) {
	parent := parentScriptWithAgentTool(
		ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"任务A"}`},
		ToolCallSpec{ID: "p2", Name: PersonaCAD, Arguments: `{"request":"任务B"}`},
	)
	ag := newOrchestrator(t, parent, childScript(), []tool.BaseTool{echoTool(t)})

	ch, err := ag.Run(context.Background(), "sess-ids", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	var ids []string
	for _, ev := range evs {
		if ev.Type != EventSubagentStatus || !strings.Contains(payloadString(t, ev, "status"), "started") {
			continue
		}
		ids = append(ids, ev.SubagentID)
	}
	if len(ids) != 2 || ids[0] != "sa_1_1" || ids[1] != "sa_1_2" {
		t.Fatalf("subagentId 序列 = %v, want [sa_1_1 sa_1_2]", ids)
	}
}

// TestAgentToolEventsLoggedAndParentTurnNotDoubleCounted：子事件打标落盘（同一
// JSONL），父 turn 计数不因子事件 turn/start 翻倍；两次 Run turn 递增。
func TestAgentToolEventsLoggedAndParentTurnNotDoubleCounted(t *testing.T) {
	store := NewEventStore(t.TempDir())
	ag := newOrchestrator(t,
		parentScriptWithAgentTool(ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"hi"}`}),
		childScript(),
		[]tool.BaseTool{echoTool(t)},
	)
	ag.store = store

	for want := 1; want <= 2; want++ {
		ch, err := ag.Run(context.Background(), "sess-log", "q")
		if err != nil {
			t.Fatalf("Run %d: %v", want, err)
		}
		evs := collect(t, ch)
		for _, ev := range evs {
			if ev.Turn != want {
				t.Fatalf("run %d 产生 Turn=%d 事件（%s）", want, ev.Turn, ev.Type)
			}
		}
		// 子事件确实落盘（含标签）
		loaded, err := store.Load("sess-log")
		if err != nil {
			t.Fatalf("Load: %v", err)
		}
		var sawChild bool
		for _, ev := range loaded {
			if ev.SubagentID != "" {
				sawChild = true
			}
		}
		if !sawChild {
			t.Fatalf("子事件未落盘（无 SubagentID 标签行）")
		}
	}
}

// TestProjectSkipsSubagentEvents：Project 投影跳过子事件（子内容经 AgentAsTool
// 工具结果回流父模型，直接注入会重复）。
func TestProjectSkipsSubagentEvents(t *testing.T) {
	store := NewEventStore(t.TempDir())
	ag := newOrchestrator(t,
		parentScriptWithAgentTool(ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"hi"}`}),
		childScript(),
		[]tool.BaseTool{echoTool(t)},
	)
	ag.store = store

	ch, err := ag.Run(context.Background(), "sess-proj", "问题")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	collect(t, ch)

	loaded, err := store.Load("sess-proj")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	msgs := Project(loaded)
	// 期望：user / assistant(tool_calls) / tool(AgentAsTool 结果) / assistant(汇总)
	if len(msgs) != 4 {
		t.Fatalf("projected %d messages, want 4（子事件被跳过）: %v", len(msgs), msgs)
	}
	for _, m := range msgs {
		if strings.Contains(m["role"].(string), "tool") && strings.Contains(m["content"].(string), "子工具结果") {
			t.Fatalf("子工具结果泄漏进投影: %v", m)
		}
	}
}

// TestAgentToolChildInheritsParentSessionBinding：AgentAsTool 子 agent 工具经
// SessionIDFromContext 继承父会话绑定（探针已验证 RunPath 子事件 + ctx 链保留）。
func TestAgentToolChildInheritsParentSessionBinding(t *testing.T) {
	sidTool, err := newStringTool("read_sid", func(ctx context.Context) (string, error) {
		return "sid=" + SessionIDFromContext(ctx), nil
	})
	if err != nil {
		t.Fatal(err)
	}
	child := Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "read_sid", Arguments: `{}`}}},
		{Chunks: []string{"子完成"}},
	}}
	ag := newOrchestrator(t,
		parentScriptWithAgentTool(ToolCallSpec{ID: "p1", Name: PersonaIFC, Arguments: `{"request":"hi"}`}),
		child,
		[]tool.BaseTool{sidTool},
	)

	ch, err := ag.Run(context.Background(), "sess-binding", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	// 子窗口内的 read_sid tool/result 应含父会话 id
	iStart, _ := findStatus(t, evs, "started")
	iFin, _ := findStatus(t, evs, "finished")
	var got string
	for i := iStart; i <= iFin; i++ {
		if evs[i].Type == EventToolResult && payloadString(t, evs[i], "name") == "read_sid" {
			got = payloadString(t, evs[i], "content")
		}
	}
	if !strings.Contains(got, "sess-binding") {
		t.Fatalf("子 read_sid 结果 = %q, want 含父会话 id（kind 路由继承）", got)
	}
}
