// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools_routing_test.go：kind 感知路由端到端——工具面（dxf 会话工具只打
// cad 后端）与 notify 面（dirty 管线 discard/stage/run/save 全走 cad），
// 双 fake 零交叉钉死；create_project 不触发对绑定模型的 notify。
package api

import (
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/store"
)

// --- kind 路由：工具面 + notify 面（双 fake 零交叉） ---

// TestKindRoutingToolsEndToEnd：绑定 dxf 模型的会话，agent 工具只打 cad 后端；
// ifc 后端零调用（双 fake 钉死）。
func TestKindRoutingToolsEndToEnd(t *testing.T) {
	ifcFB := newFakePy2(t)
	cadFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "get_script", Arguments: `{}`}}},
		{Chunks: []string{"读到了"}},
	}}, ifcFB, cadFB)
	m, err := h.deps.St.CreateWithKind("plan.dxf", 4, strings.NewReader("fake"), store.KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	cadFB.set(http.MethodGet, "/models/"+m.ID+"/script", `{"script":"PARAMS = {}"}`)
	cs, err := doChatCreate(h, fmt.Sprintf(`{"title":"t","modelId":"%s"}`, m.ID))
	if err != nil {
		t.Fatal(err)
	}
	if code := postChat(t, h, cs.ID, "读脚本"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	// 订阅并排空到 session.idle：turn 收尾（notify 判定在 consumeRun 内同步完成），
	// 避免 TempDir 清理与异步推帧/后端调用竞争（异步写盘纪律）。
	ch := h.subscribe(cs.ID)
	frames := collectUntil(t, ch, "session.idle")
	_ = frames
	deadline := time.Now().Add(5 * time.Second)
	for cadFB.count() == 0 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if cadFB.count() == 0 {
		t.Fatal("dxf 会话的工具未打到 cad 后端")
	}
	if ifcFB.count() != 0 {
		t.Fatalf("ifc 后端被命中 %d 次（dxf 会话工具面不得交叉）", ifcFB.count())
	}
}

// TestKindRoutingNotifyDXF：dxf 会话 stage_script 工具成功置 dirty →
// turn 结束 notify 管线（discard/stage/run/save）全部走 cad 后端，ifc 零调用。
func TestKindRoutingNotifyDXF(t *testing.T) {
	ifcFB := newFakePy2(t)
	cadFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "stage_script", Arguments: `{"script":"PARAMS = {}\n"}`}}},
		{Chunks: []string{"已暂存"}},
	}}, ifcFB, cadFB)
	m, err := h.deps.St.CreateWithKind("plan.dxf", 4, strings.NewReader("fake"), store.KindDXF)
	if err != nil {
		t.Fatal(err)
	}
	// notify 管线路由预置：discard(stage)/run/save + save 版本解析 fallback
	cadFB.set(http.MethodDelete, "/models/"+m.ID+"/pending", `{"discarded":0}`)
	cadFB.set(http.MethodPut, "/models/"+m.ID+"/script", `{"staged":1}`)
	cadFB.set(http.MethodPost, "/models/"+m.ID+"/script/run", `{"ok":true}`)
	cadFB.set(http.MethodPost, "/models/"+m.ID+"/script/save", `{"version":"v1"}`)
	cs, err := doChatCreate(h, fmt.Sprintf(`{"title":"t","modelId":"%s"}`, m.ID))
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "暂存脚本"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	frame := waitChatEventAny(t, ch, []string{"viewer.committed", "viewer.notify_failed"}, 8*time.Second)
	if strings.Contains(frame, "notify_failed") {
		t.Fatalf("notify 管线失败: %s", frame)
	}
	deadline := time.Now().Add(2 * time.Second)
	for cadFB.count() < 3 && time.Now().Before(deadline) {
		time.Sleep(10 * time.Millisecond)
	}
	if cadFB.count() < 3 {
		t.Fatalf("cad 后端命中 %d 次，want ≥3（discard/stage/run/save 管线未走 cad）", cadFB.count())
	}
	if ifcFB.count() != 0 {
		t.Fatalf("ifc 后端被命中 %d 次（notify 面不得交叉）", ifcFB.count())
	}
}

// TestCreateProjectDoesNotTriggerNotifyOnBoundModel：会话绑定模型 A 时 agent 调
// create_project 建模型 B——turn 结束不得对 A 跑 notify 管线（A 未变更；
// 错绑会让 stale staging 的 A 被 save 出无意图版本）。双后端 fake 零调用钉死。
func TestCreateProjectDoesNotTriggerNotifyOnBoundModel(t *testing.T) {
	ifcFB := newFakePy2(t)
	cadFB := newFakePy2(t)
	h, _ := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "create_project", Arguments: `{"title":"另一个项目"}`}}},
		{Chunks: []string{"建好了"}},
	}}, ifcFB, cadFB)
	// 绑定模型 A（ifc kind；lastCheck 零值会让 mtime 兜底也判 dirty——经 REST 建会话保证 lastCheck 已置）
	m, err := h.deps.St.CreateWithKind("bound.ifc", 4, strings.NewReader("fake"), store.KindIFC)
	if err != nil {
		t.Fatal(err)
	}
	cs, err := doChatCreate(h, fmt.Sprintf(`{"title":"t","modelId":"%s"}`, m.ID))
	if err != nil {
		t.Fatal(err)
	}
	if code := postChat(t, h, cs.ID, "再建一个新项目"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	// 排空到 session.idle（turn 收尾 + notify 判定同步完成），避免 TempDir 清理竞争
	ch := h.subscribe(cs.ID)
	frames := collectUntil(t, ch, "session.idle")
	_ = frames
	// 断言零变更调用：唯一允许的后端触达是 W-0016 的只读版本探测
	//（GET /scripts，无脚本时 404 降级不注入）——notify 管线的变更调用
	//（DELETE pending / PUT script / run / save）一次都不许出现。
	for _, c := range ifcFB.snapshot() {
		if strings.Contains(c, "DELETE") || strings.Contains(c, "PUT") ||
			strings.Contains(c, "/script/run") || strings.Contains(c, "/script/save") {
			t.Fatalf("绑定模型 A 收到变更调用 %q（create_project 不得触发对 A 的 notify 管线）；全部调用: %v", c, ifcFB.snapshot())
		}
	}
	if cadFB.count() != 0 {
		t.Fatalf("cad 后端被命中 %d 次", cadFB.count())
	}
	// 会话未置 dirty（markDirty 若被 create_project 误调会在此暴露）
	h.mu.RLock()
	dirty := cs.dirty
	h.mu.RUnlock()
	if dirty {
		t.Fatal("create_project 后会话不应置 dirty（错绑源头）")
	}
}

// waitChatEventAny 等任一指定类型事件帧（超时失败）。
func waitChatEventAny(t *testing.T, ch chan []byte, wantTypes []string, timeout time.Duration) string {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		select {
		case frame := <-ch:
			for _, w := range wantTypes {
				if strings.Contains(string(frame), "event: "+w) {
					return string(frame)
				}
			}
		case <-time.After(10 * time.Millisecond):
		}
	}
	t.Fatalf("超时未等到 %v 事件", wantTypes)
	return ""
}
