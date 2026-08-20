// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_tools_test.go：领域工具装配契约（AgentToolDeps/DomainTools/SetAgent、
// dirty 精确信号、create_project 端到端）+ 双后端测试夹具 fakePy2；
// kind 感知路由见 chat_tools_routing_test.go，工具错误单卡映射见
// chat_tools_error_test.go，runs 表条件删除见 chat_runs_race_test.go。
package api

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

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
	v, err := deps.CreateProject(ctx, "适配器项目", "")
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
	// 条件等待转换收尾（SetStatus ready，即 models.json 写盘完成）再返回——
	// CreateProject 入队异步，不等会让 t.TempDir() 清理与 worker 写盘竞态
	// （CI 慢速环境 unlinkat ... directory not empty，同 TestCreateProjectToolEndToEnd）。
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		if mm, err := h.deps.St.Get(m.ID); err == nil && mm.Status == "ready" {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}
	if mm, _ := h.deps.St.Get(m.ID); mm == nil || mm.Status != "ready" {
		t.Fatalf("骨架模型未转 ready（status=%v）", mm)
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
	// 等会话事件日志出现 idle 帧（evLog 环形缓冲不丢帧，是 turn 收尾的权威信号）：
	// consumeRun 先推 session.idle 再做 notify 判定，idle 入日志即代表事件流排空、
	// 异步写盘只剩 notify 管线（同步完成后测试才返回）——否则 t.TempDir() 清理与
	// 异步写盘竞态（CI 慢速环境复现：unlinkat ... directory not empty，PR #38）。
	// 不用 collectUntil+subscribe：订阅 channel 缓冲 16 会丢帧，慢读时收不到 idle。
	waitSessionIdleLogged(t, h, cs.ID)
}

// waitSessionIdleLogged 条件等待会话事件日志中出现 session.idle 帧（轮询 evLog）。
func waitSessionIdleLogged(t *testing.T, h *ChatHandler, cid string) {
	t.Helper()
	deadline := time.Now().Add(5 * time.Second)
	for time.Now().Before(deadline) {
		h.mu.Lock()
		logged := h.evLog[cid]
		found := false
		for _, ev := range logged {
			if strings.Contains(string(ev.frame), "event: session.idle\n") {
				found = true
				break
			}
		}
		h.mu.Unlock()
		if found {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatalf("超时未在事件日志中等到 session.idle（会话 %s）", cid)
}
