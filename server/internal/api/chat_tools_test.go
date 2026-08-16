// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools_test.go：领域工具装配（AgentToolDeps/DomainTools/SetAgent）、
// dirty 精确信号、kind 感知路由（工具面 + notify 面，双 fake 零交叉）、
// 工具错误单卡映射、runs 表条件删除。
package api

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// fakePy2 是独立于 edit_test.go fakePy 的双后端测试夹具：ifc/cad 各一份实例，
// 分别计数——kind 路由「零交叉」断言的基础。未预置路由一律 404（对齐真服务：
// 无脚本模型 GET /scripts 返回 404，W-0016 diff 上下文降级不注入——防止夹具
// 比真服务宽容导致假绿）。
type fakePy2 struct {
	mu     sync.Mutex
	calls  []string
	routes map[string]string
	srv    *httptest.Server
}

func newFakePy2(t *testing.T) *fakePy2 {
	t.Helper()
	f := &fakePy2{routes: map[string]string{}}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		f.mu.Lock()
		f.calls = append(f.calls, r.Method+" "+r.URL.Path+" "+string(b))
		resp, ok := f.routes[r.Method+" "+r.URL.Path]
		f.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		if !ok {
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"not scripted"}`)
			return
		}
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, resp)
	}))
	t.Cleanup(f.srv.Close)
	return f
}

// set 预置一条 200 响应（未预置路径 404）。
func (f *fakePy2) set(method, path, body string) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.routes[method+" "+path] = body
}

func (f *fakePy2) count() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return len(f.calls)
}

// snapshot 返回已记录调用的副本（断言用）。
func (f *fakePy2) snapshot() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := make([]string, len(f.calls))
	copy(out, f.calls)
	return out
}

// newToolsTestHandler 构造带双假后端（ifc/cad）+ store + 队列 + scripted agent
// （已注入领域工具）的 chat handler——main.go 装配顺序的测试镜像。
func newToolsTestHandler(t *testing.T, script agent.Script, fakeIFC, fakeCAD *fakePy2) (*ChatHandler, chan string) {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	runs := make(chan string, 8)
	q := convert.NewQueue(st, okRunner2{runs: runs}, 1)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q.Start(ctx)
	var ed, cad *editsvc.Client
	if fakeIFC != nil {
		ed = editsvc.New(fakeIFC.srv.URL)
	}
	if fakeCAD != nil {
		cad = editsvc.New(fakeCAD.srv.URL)
	}
	h := &ChatHandler{
		deps:     ChatDeps{Ev: agent.NewEventStore(dataDir), Ed: ed, Cad: cad, St: st, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	ag, err := agent.New(agent.LLMConfig{},
		agent.WithModel(agent.NewScriptedModel(script)),
		agent.WithStore(h.deps.Ev),
		agent.WithTools(h.DomainTools()),
	)
	if err != nil {
		t.Fatalf("agent.New: %v", err)
	}
	h.SetAgent(ag)
	return h, runs
}

// okRunner2 带计数通道的转换 runner（入队即通知测试）。
type okRunner2 struct{ runs chan string }

func (r okRunner2) Run(ctx context.Context, in, out string) error {
	if r.runs != nil {
		select {
		case r.runs <- in:
		default:
		}
	}
	return nil
}

// --- 装配契约：AgentToolDeps / DomainTools / SetAgent ---

// TestAgentToolDepsAdapters：sessionBoundModel / markSessionDirty /
// createProjectForAgent 三个适配器的接线契约（工具 → handler 回调 → 会话表）。
func TestAgentToolDepsAdapters(t *testing.T) {
	h, _ := newToolsTestHandler(t, defaultTestScript, nil, nil)
	cs := &chatSession{ID: "c_tools", AgentID: "s_tools", ModelID: "", CreatedAt: time.Now().UTC().Format(time.RFC3339)}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byAgent[cs.AgentID] = cs.ID
	h.mu.Unlock()

	deps := h.AgentToolDeps()
	if deps.SessionModel == nil || deps.MarkDirty == nil || deps.CreateProject == nil {
		t.Fatal("AgentToolDeps 三个适配器不应为 nil")
	}
	if deps.IFC != h.deps.Ed || deps.CAD != h.deps.Cad || deps.St != h.deps.St {
		t.Fatal("AgentToolDeps 未透传 Ed/Cad/St")
	}
	ctx := agent.WithSessionID(context.Background(), cs.AgentID)
	deps.MarkDirty(ctx)
	h.mu.RLock()
	dirty := cs.dirty
	h.mu.RUnlock()
	if !dirty {
		t.Fatal("MarkDirty 未把会话置 dirty")
	}
	v, err := deps.CreateProject(ctx, "适配器项目")
	if err != nil {
		t.Fatalf("CreateProject: %v", err)
	}
	m, ok := v.(*store.Model)
	if !ok || m.Name != "适配器项目.ifc" {
		t.Fatalf("CreateProject 返回 = %v", v)
	}
	if !fileExists(fmt.Sprintf("%s/uploads/%s.ifc", h.deps.DataDir, m.ID)) {
		t.Fatal("骨架 IFC 未落盘")
	}
	// 无会话上下文 / 未知会话：不 panic、不置位
	deps.MarkDirty(context.Background())
	if got := deps.SessionModel(context.Background()); got != "" {
		t.Fatalf("无会话 ctx SessionModel = %q, want 空", got)
	}
}

// TestCreateProjectToolEndToEnd：scripted agent 调 create_project 工具 →
// 骨架 IFC 落盘 + 模型注册 + 入队转换（端到端走 agent 工具面）。
func TestCreateProjectToolEndToEnd(t *testing.T) {
	h, runs := newToolsTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "c1", Name: "create_project", Arguments: `{"title":"端到端项目"}`}}},
		{Chunks: []string{"建好了"}},
	}}, nil, nil)
	cs, err := doChatCreate(h, `{"title":"t"}`)
	if err != nil {
		t.Fatal(err)
	}
	if code := postChat(t, h, cs.ID, "新建项目"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	var found *store.Model
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		ms, _ := h.deps.St.List()
		for _, m := range ms {
			if m.Name == "端到端项目.ifc" {
				found = m
			}
		}
		if found != nil {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if found == nil {
		t.Fatal("create_project 工具未注册模型")
	}
	if !fileExists(fmt.Sprintf("%s/uploads/%s.ifc", h.deps.DataDir, found.ID)) {
		t.Fatal("骨架 IFC 未落盘")
	}
	select {
	case <-runs:
	case <-time.After(2 * time.Second):
		t.Fatal("骨架模型未入队转换")
	}
}

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

// --- 工具错误单卡映射（翻译层 + 历史投影） ---

// TestTranslateToolErrorSingleCard：error 载荷的 tool/result → 工具卡片
// status:"error" + error 字段（前端 ✗ 状态），不再只靠 session.error 横幅。
func TestTranslateToolErrorSingleCard(t *testing.T) {
	tr := newEventTranslator("s_abc")
	var frames []translatedFrame
	frames = append(frames, tr.translate(ev(t, agent.EventToolCall, 1, 1,
		map[string]any{"id": "call-9", "name": "run_script", "arguments": `{}`}))...)
	frames = append(frames, tr.translate(ev(t, agent.EventToolResult, 1, 2,
		map[string]any{"id": "call-9", "name": "run_script", "error": "沙箱执行失败"}))...)
	if len(frames) != 2 {
		t.Fatalf("frames = %d, want 2", len(frames))
	}
	part, _ := frameData(t, frames[1])["part"].(map[string]any)
	st, _ := part["state"].(map[string]any)
	if st["status"] != "error" {
		t.Fatalf("state.status = %v, want error", st)
	}
	if st["error"] != "沙箱执行失败" {
		t.Fatalf("state.error = %v", st)
	}
	if _, has := st["output"]; has {
		t.Fatalf("错误态不应带 output: %v", st)
	}
	if st["input"] != `{}` {
		t.Fatalf("state.input = %v, want 保留调用参数", st)
	}
}

// TestProjectHistoryToolErrorState：历史投影同样折叠出 error 状态卡片
// （重新打开会话时错误卡片仍在）。
func TestProjectHistoryToolErrorState(t *testing.T) {
	evs := []agent.Event{
		ev(t, agent.EventTurnStart, 1, 0, map[string]any{"user": "跑一下"}),
		ev(t, agent.EventAssistantMessage, 1, 1, map[string]any{"content": ""}),
		ev(t, agent.EventToolCall, 1, 1, map[string]any{"id": "call-9", "name": "run_script", "arguments": `{}`}),
		ev(t, agent.EventToolResult, 1, 2, map[string]any{"id": "call-9", "name": "run_script", "error": "kaboom"}),
	}
	msgs := projectChatHistory(evs, "s_abc")
	var sawErr bool
	for _, m := range msgs {
		for _, p := range m.Parts {
			if p["type"] != "tool" {
				continue
			}
			st, _ := p["state"].(map[string]any)
			if st != nil && st["status"] == "error" && st["error"] == "kaboom" {
				sawErr = true
			}
		}
	}
	if !sawErr {
		t.Fatalf("历史投影未保留工具错误卡片: %v", msgs)
	}
}

// --- runs 表防御竞态：条件删除 ---

// countingModel：第一跑阻塞（等 close(release)），其后每跑立即答复收尾——
// 构造「旧 run 迟收尾 vs 新 run 已登记」的竞态窗口。
type countingModel struct {
	step    *int32
	release chan struct{}
	started chan struct{}
}

func newCountingModel(step *int32) *countingModel {
	return &countingModel{step: step, release: make(chan struct{}), started: make(chan struct{}, 4)}
}

func (m *countingModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	return m, nil
}

func (m *countingModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	n := atomic.AddInt32(m.step, 1)
	if n == 1 {
		m.started <- struct{}{}
		<-m.release // 第一跑阻塞，直到测试放行
	}
	return schema.StreamReaderFromArray([]*schema.Message{{Role: schema.Assistant, Content: "ok"}}), nil
}

func (m *countingModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	n := atomic.AddInt32(m.step, 1)
	if n == 1 {
		m.started <- struct{}{}
		<-m.release
	}
	return &schema.Message{Role: schema.Assistant, Content: "ok"}, nil
}

// TestRunsDeleteConditionalOnRunIdentity：post run1（阻塞）→ post run2（覆盖表项、
// 取消 run1）→ run1 收尾不得删 run2 的登记；run2 收尾后表项清空。
func TestRunsDeleteConditionalOnRunIdentity(t *testing.T) {
	dataDir := t.TempDir()
	evStore := agent.NewEventStore(dataDir)
	var step int32
	cm := newCountingModel(&step)
	ag, err := agent.New(agent.LLMConfig{}, agent.WithModel(cm), agent.WithStore(evStore))
	if err != nil {
		t.Fatal(err)
	}
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: evStore, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	cs, err := doChatCreate(h, `{"title":"t"}`)
	if err != nil {
		t.Fatal(err)
	}
	if code := postChat(t, h, cs.ID, "第一跑"); code != http.StatusOK {
		t.Fatalf("post1 status = %d", code)
	}
	<-cm.started // run1 模型已启动（阻塞中）
	waitForRunsCount(t, h, cs.ID, 1)
	if code := postChat(t, h, cs.ID, "第二跑"); code != http.StatusOK {
		t.Fatalf("post2 status = %d", code)
	}
	// run1 被取消 → 迟收尾；run2 已登记并完成 → 表项由 run2 自己删除。
	waitForRunsCount(t, h, cs.ID, 0)
	// 放行第一跑（其 consumeRun 现在才收尾）：表已空，无「误删/复活」可言，
	// 但不得 panic 或重新写入（run1 的 identity 已不是表内条目）。
	close(cm.release)
	// 给 run1 收尾一点时间后再断言表项仍为空（条件等待 run1 残留不出现）
	time.Sleep(50 * time.Millisecond)
	waitForRunsCount(t, h, cs.ID, 0)
}

// waitForRunsCount 条件等待 runs 表条目数（超时失败）。
func waitForRunsCount(t *testing.T, h *ChatHandler, cid string, want int) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		h.mu.RLock()
		got := 0
		if _, ok := h.runs[cid]; ok {
			got = 1
		}
		h.mu.RUnlock()
		if got == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("runs[%s] 条目数未到 %d", cid, want)
}
