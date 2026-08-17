// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// subagent_test.go：subagent-as-tool 契约——派发工具触发独立子 agent run、
// 子事件打 subagentId/parentSessionId 经同一事件通道上浮、深度预算 1（子工具面
// 无 dispatch 工具）、子 agent 继承父会话绑定（kind 路由可用）、事件日志含标签
// 且父 turn 计数不被子事件污染。
package agent

import (
	"context"
	"encoding/json"
	"strings"
	"sync"
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

// subCfgFor 构造测试用 SubagentConfig：每次派发新建 scripted 子模型（并行派发
// 互不抢位置，确定性）；子工具面 = fixture（echo + 可选探针），绝不含 dispatch 工具。
func subCfgFor(t *testing.T, script Script, extra ...tool.BaseTool) SubagentConfig {
	t.Helper()
	return SubagentConfig{
		NewModel: func() model.ToolCallingChatModel { return NewScriptedModel(script) },
		MakeTools: func(string) []tool.BaseTool {
			return append([]tool.BaseTool{echoTool(t)}, extra...)
		},
		MaxStep: 10,
	}
}

// parentScriptWithDispatch 主 agent 脚本：第一步派发（可多工具调用并行），第二步汇总。
func parentScriptWithDispatch(calls ...ToolCallSpec) Script {
	return Script{Steps: []ScriptStep{
		{ToolCalls: calls},
		{Chunks: []string{"汇总完成"}},
	}}
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

// TestSubagentDispatchEndToEnd：scripted 主 agent 产出 dispatch_ifc_agent
// tool_call → 子 run 执行（scripted 子模型）→ 子事件全部带 subagentId +
// parentSessionId 经同一通道上浮；started 先于子事件、finished 后于子事件、
// 且先于主 agent 的 dispatch tool/result；工具结果 = 子 agent 最终答复。
func TestSubagentDispatchEndToEnd(t *testing.T) {
	store := NewEventStore(t.TempDir())
	cfg := subCfgFor(t, childScript())
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":"建一堵墙"}`},
		))),
		WithTools(AsBaseTools(SubagentTools(cfg))),
		WithStore(store),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-sub", "开始")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	iStart, startEv := findStatus(t, evs, "started")
	iFin, finEv := findStatus(t, evs, "finished")
	subID := "sa_1_1"
	if startEv.SubagentID != subID || startEv.ParentSessionID != "sess-sub" {
		t.Fatalf("started 事件标签 subagentId=%q parentSessionId=%q, want %s/sess-sub",
			startEv.SubagentID, startEv.ParentSessionID, subID)
	}
	if finEv.SubagentID != subID {
		t.Fatalf("finished 事件 subagentId=%q, want %s", finEv.SubagentID, subID)
	}
	if iFin <= iStart {
		t.Fatalf("finished(%d) 应在 started(%d) 之后", iFin, iStart)
	}
	// started/finished 载荷字段
	var sp map[string]any
	if err := json.Unmarshal(startEv.Payload, &sp); err != nil {
		t.Fatal(err)
	}
	if sp["persona"] != PersonaIFC || sp["task"] != "建一堵墙" || sp["parentSessionId"] != "sess-sub" {
		t.Fatalf("started 载荷 = %v", sp)
	}

	// (started, finished) 窗口内全部事件属于该子 agent（子事件全部打标签）
	var childTypes []string
	for i := iStart + 1; i < iFin; i++ {
		if evs[i].SubagentID != subID || evs[i].ParentSessionID != "sess-sub" {
			t.Fatalf("窗口内事件 %d（%s）标签 = %q/%q, want %s/sess-sub",
				i, evs[i].Type, evs[i].SubagentID, evs[i].ParentSessionID, subID)
		}
		childTypes = append(childTypes, evs[i].Type)
	}
	joined := strings.Join(childTypes, ",")
	for _, want := range []string{EventTurnStart, EventToolCall, EventToolResult, EventAssistantChunk, EventAssistantMessage, EventTurnEnd} {
		if !strings.Contains(joined, want) {
			t.Fatalf("子事件序列缺 %s: %v", want, childTypes)
		}
	}
	// 窗口外不允许出现该 subID —— 主事件不被误标
	for i, ev := range evs {
		if i >= iStart && i <= iFin {
			continue
		}
		if ev.SubagentID == subID {
			t.Fatalf("窗口外事件 %d（%s）误带 subagentId", i, ev.Type)
		}
	}

	// dispatch tool/result 在 finished 之后，且内容 = 子 agent 最终答复
	if got := payloadString(t, evs[iFin+1], "name"); got != "dispatch_ifc_agent" || evs[iFin+1].Type != EventToolResult {
		t.Fatalf("finished 之后应为 dispatch 的 tool/result，得到 %s/%s（序列=%v）", evs[iFin+1].Type, got, eventTypes(evs))
	}
	if c := payloadString(t, evs[iFin+1], "content"); !strings.Contains(c, "子代理完成") {
		t.Fatalf("dispatch 工具结果 = %q, want 含子 agent 最终答复", c)
	}
	// 主 turn 正常收尾
	if last := evs[len(evs)-1]; last.Type != EventTurnEnd || payloadString(t, last, "message") != "汇总完成" {
		t.Fatalf("主 turn 收尾异常: %s %s", last.Type, last.Payload)
	}
}

// TestSubagentDepthBudgetStructural：深度预算 1 钉死——子 agent 工具面来自
// MakeTools，SubagentTools 的两个派发工具不在其中；子 run 实际发出的 tool/call
// 名单 ⊆ MakeTools 产出（无 dispatch_*，孙代派发结构性不可能）。
func TestSubagentDepthBudgetStructural(t *testing.T) {
	cfg := subCfgFor(t, childScript())
	childNames := toolNamesBase(t, cfg.MakeTools(PersonaIFC))
	for _, n := range childNames {
		if n == "dispatch_ifc_agent" || n == "dispatch_cad_agent" {
			t.Fatalf("子工具面含派发工具 %s（深度预算被突破）", n)
		}
	}
	dispatch := SubagentTools(cfg)
	if got := toolNames(dispatch); len(got) != 2 || got[0] != "dispatch_ifc_agent" || got[1] != "dispatch_cad_agent" {
		t.Fatalf("SubagentTools 产出 = %v, want [dispatch_ifc_agent dispatch_cad_agent]", got)
	}

	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":"x"}`},
		))),
		WithTools(AsBaseTools(dispatch)),
		WithStore(NewEventStore(t.TempDir())),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-depth", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	for _, ev := range evs {
		if ev.Type != EventToolCall || ev.SubagentID == "" {
			continue
		}
		name := payloadString(t, ev, "name")
		if name == "dispatch_ifc_agent" || name == "dispatch_cad_agent" {
			t.Fatalf("子 agent 发起了二次派发 %q（深度预算 1 被突破）", name)
		}
		if !containsStr(childNames, name) {
			t.Fatalf("子 agent 调用了工具面之外的工具 %q", name)
		}
	}
}

// TestSubagentUniqueIDsAndPersonas：同一 turn 内并行派发 ifc/cad 两个子 agent，
// subagentId 唯一（sa_1_1 / sa_1_2）且 persona 正确。
func TestSubagentUniqueIDsAndPersonas(t *testing.T) {
	cfg := subCfgFor(t, childScript())
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":"a"}`},
			ToolCallSpec{ID: "d2", Name: "dispatch_cad_agent", Arguments: `{"task":"b"}`},
		))),
		WithTools(AsBaseTools(SubagentTools(cfg))),
		WithStore(NewEventStore(t.TempDir())),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-two", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)

	ids := map[string]string{} // subagentId → persona
	for _, ev := range evs {
		if ev.Type != EventSubagentStatus {
			continue
		}
		var p map[string]any
		if err := json.Unmarshal(ev.Payload, &p); err != nil {
			t.Fatal(err)
		}
		if s, _ := p["status"].(string); s != "started" {
			continue
		}
		persona, _ := p["persona"].(string)
		ids[ev.SubagentID] = persona
	}
	if len(ids) != 2 {
		t.Fatalf("派发子 agent 数 = %d (%v), want 2", len(ids), ids)
	}
	if ids["sa_1_1"] == "" || ids["sa_1_2"] == "" {
		t.Fatalf("subagentId 应为 sa_1_1/sa_1_2，得到 %v", ids)
	}
	personas := map[string]bool{ids["sa_1_1"]: true, ids["sa_1_2"]: true}
	if !personas[PersonaIFC] || !personas[PersonaCAD] {
		t.Fatalf("persona 集合 = %v, want ifc+cad", ids)
	}
}

// TestSubagentEventsLoggedAndParentTurnNotDoubleCounted：子事件带标签写入父会话
// JSONL；下一次父 Run 的 turn 计数不被子 turn/start 污染（=2 而非 3）。
func TestSubagentEventsLoggedAndParentTurnNotDoubleCounted(t *testing.T) {
	store := NewEventStore(t.TempDir())
	cfg := subCfgFor(t, Script{Steps: []ScriptStep{{Chunks: []string{"子答复"}}}})
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_cad_agent", Arguments: `{"task":"x"}`},
		))),
		WithTools(AsBaseTools(SubagentTools(cfg))),
		WithStore(store),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-log", "第一轮")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	collect(t, ch)

	loaded, err := store.Load("sess-log")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	tagged := 0
	for _, ev := range loaded {
		if ev.SubagentID != "" {
			tagged++
		}
	}
	if tagged == 0 {
		t.Fatal("事件日志未包含带 subagentId 的子事件")
	}

	// 第二轮（无派发）：父 turn 应为 2——子 turn/start 不计入
	ch2, err := ag.Run(context.Background(), "sess-log", "第二轮")
	if err != nil {
		t.Fatalf("Run2: %v", err)
	}
	evs2 := collect(t, ch2)
	for _, ev := range evs2 {
		if ev.SubagentID != "" {
			continue
		}
		if ev.Turn != 2 {
			t.Fatalf("第二轮父事件 turn = %d, want 2（子 turn/start 被误计入）", ev.Turn)
		}
	}
}

// TestProjectSkipsSubagentEvents：Project 折叠模型上下文时跳过子事件——子内容
// 经 dispatch 工具结果回流父模型，不重复注入。
func TestProjectSkipsSubagentEvents(t *testing.T) {
	evs := []Event{
		{Type: EventTurnStart, Turn: 1, Payload: jsonPayload(map[string]any{"user": "问题"})},
		{Type: EventSubagentStatus, Turn: 1, SubagentID: "sa_1_1", Payload: jsonPayload(map[string]any{"status": "started"})},
		{Type: EventAssistantMessage, Turn: 1, Step: 1, SubagentID: "sa_1_1",
			Payload: jsonPayload(map[string]any{"content": "子的中间答复"})},
		{Type: EventToolResult, Turn: 1, Step: 2,
			Payload: jsonPayload(map[string]any{"id": "d1", "name": "dispatch_ifc_agent", "content": "子的最终报告"})},
		{Type: EventAssistantMessage, Turn: 1, Step: 3,
			Payload: jsonPayload(map[string]any{"content": "主答复"})},
	}
	msgs := Project(evs)
	if len(msgs) != 3 { // user / tool(dispatch 结果) / assistant
		t.Fatalf("Project 折叠出 %d 条, want 3: %v", len(msgs), msgs)
	}
	for _, m := range msgs {
		if c, _ := m["content"].(string); c == "子的中间答复" {
			t.Fatalf("子事件泄漏进模型上下文: %v", msgs)
		}
	}
}

// TestSubagentNoHubReturnsErrorText：脱离父 Run 上下文直接调用派发工具——
// 错误文本化返回（不抛 Go error、不 panic）。
func TestSubagentNoHubReturnsErrorText(t *testing.T) {
	cfg := subCfgFor(t, childScript())
	out := invoke(t, SubagentTools(cfg), "dispatch_ifc_agent", `{"task":"x"}`)
	if !strings.Contains(out, "派发失败") {
		t.Fatalf("无父上下文调用应返回派发失败文本，得到 %q", out)
	}
}

// TestSubagentEmptyTaskRejected：空 task 错误文本化（子 run 不启动）。
func TestSubagentEmptyTaskRejected(t *testing.T) {
	cfg := subCfgFor(t, childScript())
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":""}`},
		))),
		WithTools(AsBaseTools(SubagentTools(cfg))),
		WithStore(NewEventStore(t.TempDir())),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-empty", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	evs := collect(t, ch)
	for _, ev := range evs {
		if ev.Type != EventSubagentStatus {
			continue
		}
		t.Fatalf("空 task 不应产生 subagent/status 事件: %s", ev.Payload)
	}
	// dispatch 的 tool/result 应含 task 错误说明
	var result string
	for _, ev := range evs {
		if ev.Type == EventToolResult && payloadString(t, ev, "name") == "dispatch_ifc_agent" {
			result = payloadString(t, ev, "content")
		}
	}
	if !strings.Contains(result, "task") {
		t.Fatalf("空 task 的工具结果应含错误说明，得到 %q（序列=%v）", result, eventTypes(evs))
	}
}

// sessionProbe 记录工具调用时 ctx 解析出的会话 id（子 agent 绑定继承断言）。
type sessionProbe struct {
	mu   sync.Mutex
	seen []string
}

func (p *sessionProbe) record(s string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.seen = append(p.seen, s)
}

func (p *sessionProbe) snapshot() []string {
	p.mu.Lock()
	defer p.mu.Unlock()
	out := make([]string, len(p.seen))
	copy(out, p.seen)
	return out
}

// TestSubagentChildInheritsParentSessionBinding：子 agent 工具经
// SessionIDFromContext 解析到的是父会话 id（kind 路由 / 会话绑定模型可用），
// 而非子 run 的日志 session id。
func TestSubagentChildInheritsParentSessionBinding(t *testing.T) {
	probe := &sessionProbe{}
	probeTool, err := newStringTool("probe", func(ctx context.Context) (string, error) {
		probe.record(SessionIDFromContext(ctx))
		return "probe-ok", nil
	})
	if err != nil {
		t.Fatal(err)
	}
	cfg := subCfgFor(t, Script{Steps: []ScriptStep{
		{ToolCalls: []ToolCallSpec{{ID: "cc-1", Name: "probe", Arguments: `{}`}}},
		{Chunks: []string{"子完成"}},
	}}, probeTool)
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(parentScriptWithDispatch(
			ToolCallSpec{ID: "d1", Name: "dispatch_ifc_agent", Arguments: `{"task":"x"}`},
		))),
		WithTools(AsBaseTools(SubagentTools(cfg))),
		WithStore(NewEventStore(t.TempDir())),
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	ch, err := ag.Run(context.Background(), "sess-bind", "go")
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	collect(t, ch)
	seen := probe.snapshot()
	if len(seen) == 0 {
		t.Fatal("子 agent 未执行 probe 工具")
	}
	for _, s := range seen {
		if s != "sess-bind" {
			t.Fatalf("子工具解析会话 = %q, want 父会话 sess-bind", s)
		}
	}
}

// --- helpers ---

func toolNamesBase(t *testing.T, ts []tool.BaseTool) []string {
	t.Helper()
	var names []string
	for _, tl := range ts {
		info, err := tl.Info(context.Background())
		if err != nil {
			continue
		}
		names = append(names, info.Name)
	}
	return names
}

func containsStr(list []string, s string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}
