// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_staged_test.go：run_script 中途预览契约——viewer.staged SSE 事件
// （载荷严格 {modelId, kind}，主会话事件无 subagentId）+ 工具结果 staging
// diff 摘要 + run 失败不推事件。
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/store"
)

// sseFrameData 解出一条 SSE 帧的 data JSON（pushSystem 帧形：
// "id: N\nevent: <type>\ndata: {...}\n\n"）。
func sseFrameData(t *testing.T, frame string) map[string]any {
	t.Helper()
	idx := strings.Index(frame, "data: ")
	if idx < 0 {
		t.Fatalf("帧缺 data 行: %q", frame)
	}
	var d map[string]any
	if err := json.Unmarshal([]byte(strings.TrimSpace(frame[idx+len("data: "):])), &d); err != nil {
		t.Fatalf("data 非 JSON: %v（帧 %q）", err, frame)
	}
	return d
}

// assertViewerStagedPayload 钉 viewer.staged 载荷契约：严格 {modelId, kind}
// 两字段，无 subagentId（主会话事件形状不回归）。
func assertViewerStagedPayload(t *testing.T, frame, wantModel, wantKind string) {
	t.Helper()
	d := sseFrameData(t, frame)
	if d["modelId"] != wantModel || d["kind"] != wantKind {
		t.Fatalf("viewer.staged 载荷 = %v, want {modelId:%s kind:%s}", d, wantModel, wantKind)
	}
	if _, has := d["subagentId"]; has {
		t.Fatalf("主会话 viewer.staged 不得带 subagentId: %v", d)
	}
	if len(d) != 2 {
		t.Fatalf("viewer.staged 载荷字段数 = %d, want 2（严格 {modelId, kind}）: %v", len(d), d)
	}
}

// runStagedScript 起一条绑定 modelID 的会话并下发消息触发 scripted run_script，
// 返回订阅帧（排空到 session.idle）与帧 channel（供后续终态事件等待）。
func runStagedScript(t *testing.T, h *ChatHandler, modelID string) ([]string, chan []byte, string) {
	t.Helper()
	cs, err := doChatCreate(h, fmt.Sprintf(`{"title":"t","modelId":"%s"}`, modelID))
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "跑一下"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	return collectUntil(t, ch, "session.idle"), ch, cs.ID
}

// TestRunScriptPushesViewerStagedIFC：scripted agent run_script 成功 →
// SSE 收到 viewer.staged（{modelId, kind:ifc}，无 subagentId），工具结果含
// staging diff 摘要（added/removed 计数 + PARAMS 变化行）。
func TestRunScriptPushesViewerStagedIFC(t *testing.T) {
	ifcFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "run_script", Arguments: `{}`}}},
		{Chunks: []string{"跑完了"}},
	}}, ifcFB, nil)
	m, err := h.deps.St.CreateWithKind("a.ifc", 4, strings.NewReader("fake"), store.KindIFC)
	if err != nil {
		t.Fatal(err)
	}
	ifcFB.set(http.MethodPost, "/models/"+m.ID+"/script/run", `{"ok":true}`)
	ifcFB.set(http.MethodGet, "/models/"+m.ID+"/script/staging/diff",
		`{"from":0,"to":1,"text_diff":"","stats":{"added":2,"removed":1},`+
			`"params_changes":[{"key":"width","action":"modified","old":3,"new":4}]}`)
	frames, ch, _ := runStagedScript(t, h, m.ID)

	var staged string
	for _, f := range frames {
		if strings.Contains(f, "event: viewer.staged") {
			staged = f
		}
	}
	if staged == "" {
		t.Fatalf("未收到 viewer.staged:\n%s", strings.Join(frames, "---\n"))
	}
	assertViewerStagedPayload(t, staged, m.ID, "ifc")

	joined := strings.Join(frames, "\n")
	if !strings.Contains(joined, "added=2") || !strings.Contains(joined, "width") {
		t.Fatalf("工具结果帧缺 staging diff 摘要:\n%s", joined)
	}
	// run_script 置 dirty → idle 后 notify 管线必出终态事件（fake 未预置管线
	// 路由 → notify_failed）；等它收尾再返回，防 TempDir 清理与异步写盘竞态。
	waitChatEventAny(t, ch, []string{"viewer.committed", "viewer.notify_failed"}, 8*time.Second)
}

// TestRunScriptPushesViewerStagedDXF：dxf 模型走 cad 后端，viewer.staged
// 载荷 kind=dxf（web 按 kind 分流刷新的对接契约）。
func TestRunScriptPushesViewerStagedDXF(t *testing.T) {
	ifcFB := newFakePy2(t)
	cadFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "run_script", Arguments: `{}`}}},
		{Chunks: []string{"跑完了"}},
	}}, ifcFB, cadFB)
	m, err := h.deps.St.CreateWithKind("plan.dxf", 4, strings.NewReader("fake"), store.KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	cadFB.set(http.MethodPost, "/models/"+m.ID+"/script/run", `{"ok":true}`)
	cadFB.set(http.MethodGet, "/models/"+m.ID+"/script/staging/diff",
		`{"from":0,"to":1,"text_diff":"","stats":{"added":1,"removed":0},"params_changes":[]}`)
	frames, ch, _ := runStagedScript(t, h, m.ID)

	var staged string
	for _, f := range frames {
		if strings.Contains(f, "event: viewer.staged") {
			staged = f
		}
	}
	if staged == "" {
		t.Fatalf("未收到 viewer.staged:\n%s", strings.Join(frames, "---\n"))
	}
	assertViewerStagedPayload(t, staged, m.ID, "dxf")
	if ifcFB.count() != 0 {
		t.Fatalf("ifc 后端被命中 %d 次（dxf 模型 run/diff 不得交叉）", ifcFB.count())
	}
	waitChatEventAny(t, ch, []string{"viewer.committed", "viewer.notify_failed"}, 8*time.Second)
}

// TestRunScriptFailureNoViewerStaged：run_script 失败（后端 4xx）→ 整个 turn
// 不得出现 viewer.staged 事件（预览信号只对成功落地负责）。
func TestRunScriptFailureNoViewerStaged(t *testing.T) {
	ifcFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "run_script", Arguments: `{}`}}},
		{Chunks: []string{"失败了"}},
	}}, ifcFB, nil)
	m, err := h.deps.St.CreateWithKind("a.ifc", 4, strings.NewReader("fake"), store.KindIFC)
	if err != nil {
		t.Fatal(err)
	}
	// 不预置 run 路由 → fake 404 → 工具错误文本化（run 失败路径）
	frames, _, _ := runStagedScript(t, h, m.ID)
	for _, f := range frames {
		if strings.Contains(f, "event: viewer.staged") {
			t.Fatalf("run 失败不应推 viewer.staged:\n%s", strings.Join(frames, "---\n"))
		}
	}
}

// TestAgentToolDepsPushStagedAdapter：PushStaged 适配器接线契约——非 nil；
// 无会话 ctx 不推不 panic；已知会话经 pushSystem 推出严格 {modelId, kind} 载荷。
func TestAgentToolDepsPushStagedAdapter(t *testing.T) {
	h, _ := newToolsTestHandler(t, defaultTestScript, nil, nil)
	cs := &chatSession{ID: "c_staged", AgentID: "s_staged", CreatedAt: time.Now().UTC().Format(time.RFC3339)}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byAgent[cs.AgentID] = cs.ID
	h.mu.Unlock()

	deps := h.AgentToolDeps()
	if deps.PushStaged == nil {
		t.Fatal("AgentToolDeps.PushStaged 不应为 nil")
	}
	ch := h.subscribe(cs.ID)
	// 无会话上下文 / 未知会话：不 panic、不推帧
	deps.PushStaged(context.Background(), "m_0000000000000000", "ifc")
	deps.PushStaged(agent.WithSessionID(context.Background(), "s_unknown"), "m_0000000000000000", "ifc")
	deps.PushStaged(agent.WithSessionID(context.Background(), cs.AgentID), "m_0123456789abcdef", "dxf")
	frame := string(waitChatEvent(t, ch, "viewer.staged"))
	assertViewerStagedPayload(t, frame, "m_0123456789abcdef", "dxf")
	select {
	case extra := <-ch:
		t.Fatalf("无会话 ctx 的 PushStaged 泄漏了帧: %q", extra)
	default:
	}
}
