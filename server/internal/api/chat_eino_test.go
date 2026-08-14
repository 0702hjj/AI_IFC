// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// newEinoTestHandler 构造带 scripted agent（指定脚本）的 chat handler。
func newEinoTestHandler(t *testing.T, script agent.Script) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	ag, st := newChatTestAgent(t, dataDir, script)
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: st, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]context.CancelFunc{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// postChat 经 mux 发一条消息，返回 HTTP 状态码。
func postChat(t *testing.T, h *ChatHandler, cid, text string) int {
	t.Helper()
	body := `{"text":` + strconv_(text) + `}`
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cid+"/messages", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	return rec.Code
}

func strconv_(s string) string {
	raw, _ := json.Marshal(s)
	return string(raw)
}

// collectUntil 收帧直到出现指定事件类型（返回含该帧在内的全部帧），超时失败。
func collectUntil(t *testing.T, ch chan []byte, wantType string) []string {
	t.Helper()
	var frames []string
	deadline := time.Now().Add(5 * time.Second)
	for {
		select {
		case f := <-ch:
			frames = append(frames, string(f))
			if strings.Contains(string(f), "event: "+wantType+"\n") {
				return frames
			}
		case <-time.After(10 * time.Millisecond):
			if time.Now().After(deadline) {
				t.Fatalf("超时未等到 %s，已收帧:\n%s", wantType, strings.Join(frames, "---\n"))
			}
		}
	}
}

func frameEvent(frame string) string {
	for _, line := range strings.Split(frame, "\n") {
		if strings.HasPrefix(line, "event: ") {
			return strings.TrimPrefix(line, "event: ")
		}
	}
	return ""
}

func frameID(frame string) string {
	for _, line := range strings.Split(frame, "\n") {
		if strings.HasPrefix(line, "id: ") {
			return strings.TrimPrefix(line, "id: ")
		}
	}
	return ""
}

// TestPostMessageStreamsContractFrames：端到端——post 一条消息，浏览器应收到与
// opencode 时代完全一致的 SSE 序列：busy → message.updated(user) → message.updated(assistant)
// → part.updated(text) → part.delta×2 → session.status idle → session.idle，且帧 id 递增。
func TestPostMessageStreamsContractFrames(t *testing.T) {
	h := newEinoTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{Chunks: []string{"你好", "，世界"}},
	}})
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_aaaaaaaaaaaaaaaa"}`)
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)

	if code := postChat(t, h, cs.ID, "打个招呼"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	frames := collectUntil(t, ch, "session.idle")

	var events []string
	for _, f := range frames {
		events = append(events, frameEvent(f))
	}
	want := []string{
		"session.status", "message.updated", "message.updated",
		"message.part.updated", "message.part.delta", "message.part.delta",
		"session.status", "session.idle",
	}
	if strings.Join(events, "|") != strings.Join(want, "|") {
		t.Fatalf("SSE 事件序列 = %v, want %v", events, want)
	}
	// 帧 id 从 1 递增
	for i, f := range frames {
		if got := frameID(f); got != strings.TrimPrefix(strings.TrimPrefix(itoa(i+1), ""), "") {
			t.Fatalf("帧[%d] id = %q, want %d", i, got, i+1)
		}
	}
	// busy → idle 状态对
	if !strings.Contains(frames[0], `"type":"busy"`) {
		t.Fatalf("首帧应为 session.status busy: %s", frames[0])
	}
	if !strings.Contains(frames[len(frames)-2], `"type":"idle"`) {
		t.Fatalf("倒数第二帧应为 session.status idle: %s", frames[len(frames)-2])
	}
	// delta 逐片且累加为完整答复
	if !strings.Contains(frames[4], `"delta":"你好"`) || !strings.Contains(frames[5], `"delta":"，世界"`) {
		t.Fatalf("delta 帧内容不符: %s | %s", frames[4], frames[5])
	}
}

func itoa(n int) string {
	return strings.TrimSpace(jsonNumber(n))
}

func jsonNumber(n int) string {
	raw, _ := json.Marshal(n)
	return string(raw)
}

// TestGetMessagesProjectsRunHistory：一轮跑完后 GET messages 从事件日志投影出
// user + assistant 两条消息（重新打开会话的回填契约）。
func TestGetMessagesProjectsRunHistory(t *testing.T) {
	h := newEinoTestHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{Chunks: []string{"已", "完成"}},
	}})
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_bbbbbbbbbbbbbbbb"}`)
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "改一下"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	collectUntil(t, ch, "session.idle")

	req := httptest.NewRequest(http.MethodGet, "/api/v1/chat/sessions/"+cs.ID+"/messages", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("get messages status = %d body = %s", rec.Code, rec.Body)
	}
	var e env
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil {
		t.Fatal(err)
	}
	var msgs []struct {
		Info  map[string]any   `json:"info"`
		Parts []map[string]any `json:"parts"`
	}
	if err := json.Unmarshal(e.Data, &msgs); err != nil {
		t.Fatalf("history decode: %v data=%s", err, e.Data)
	}
	if len(msgs) != 2 {
		t.Fatalf("history msgs = %d, want 2: %s", len(msgs), e.Data)
	}
	if msgs[0].Info["role"] != "user" || msgs[0].Parts[0]["type"] != "text" {
		t.Fatalf("msg0 = %v", msgs[0])
	}
	if !strings.Contains(msgs[0].Parts[0]["text"].(string), "[用户需求] 改一下") {
		t.Fatalf("user part 应含注入后的完整 prompt: %v", msgs[0].Parts[0])
	}
	if msgs[1].Info["role"] != "assistant" || msgs[1].Parts[0]["text"] != "已完成" {
		t.Fatalf("msg1 = %v, want assistant 全量文本 已完成", msgs[1])
	}
}

// TestPostMessageTurnEndTriggersNotify：agent loop 结束 + 工作区 IFC 被改（mtime 新于
// lastCheck）→ notify 管线照常触发（无脚本路径：DELETE pending → 重转 → viewer.committed）。
func TestPostMessageTurnEndTriggersNotify(t *testing.T) {
	py, pyURL := newFakePy(t)
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	runs := make(chan string, 4)
	q := convert.NewQueue(st, spyRunner{runs: runs}, 1)
	ctx, cancel := context.WithCancel(context.Background())
	t.Cleanup(cancel)
	q.Start(ctx)
	ag, evStore := newChatTestAgent(t, dataDir, defaultTestScript)
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: evStore, Ed: editsvc.New(pyURL), St: st, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]context.CancelFunc{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()

	m, err := st.Create("m.ifc", 4, strings.NewReader("fake"))
	if err != nil {
		t.Fatal(err)
	}
	py.set("DELETE", "/models/"+m.ID+"/pending", 200, `{"discarded":0}`)

	cs, err := doChatCreate(h, `{"title":"t","modelId":"`+m.ID+`"}`)
	if err != nil {
		t.Fatal(err)
	}
	// 工作区 IFC mtime 晚于会话 lastCheck → 视为被 agent 改过
	future := time.Now().Add(time.Minute)
	if err := os.Chtimes(filepath.Join(dataDir, "uploads", m.ID+".ifc"), future, future); err != nil {
		t.Fatal(err)
	}

	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "改墙"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	frames := collectUntil(t, ch, "viewer.committed")

	// viewer.committed 必须在 session.idle 之后（notify 是 turn 结束后的触发）
	var idleIdx, committedIdx = -1, -1
	for i, f := range frames {
		switch frameEvent(f) {
		case "session.idle":
			idleIdx = i
		case "viewer.committed":
			committedIdx = i
		}
	}
	if idleIdx < 0 || committedIdx < 0 || committedIdx < idleIdx {
		t.Fatalf("帧顺序错误（idle=%d committed=%d）:\n%s", idleIdx, committedIdx, strings.Join(frames, "---\n"))
	}
	waitRun(t, runs)
	waitReady(t, st, m.ID)
}

// --- abort ---

// blockingModel 阻塞在 ctx 取消的模型（abort 测试：turn 不主动结束）。
type blockingModel struct {
	once    sync.Once
	started chan struct{}
}

func newBlockingModel() *blockingModel { return &blockingModel{started: make(chan struct{})} }

func (m *blockingModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	return m, nil
}

func (m *blockingModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	m.once.Do(func() { close(m.started) })
	<-ctx.Done()
	return nil, ctx.Err()
}

func (m *blockingModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	m.once.Do(func() { close(m.started) })
	<-ctx.Done()
	return nil, ctx.Err()
}

// TestAbortCancelsRun：busy 中 abort → 运行被取消，浏览器收到 session.idle 收尾，
// 且不刷 session.error（主动中止是正常控制流）。
func TestAbortCancelsRun(t *testing.T) {
	bm := newBlockingModel()
	dataDir := t.TempDir()
	evStore := agent.NewEventStore(dataDir)
	ag, err := agent.New(agent.LLMConfig{}, agent.WithModel(bm), agent.WithStore(evStore))
	if err != nil {
		t.Fatal(err)
	}
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: evStore, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]context.CancelFunc{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()

	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_cccccccccccccccc"}`)
	if err != nil {
		t.Fatal(err)
	}
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "慢慢想"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	select {
	case <-bm.started:
	case <-time.After(3 * time.Second):
		t.Fatal("模型未开始运行")
	}

	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/abort", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("abort status = %d body = %s", rec.Code, rec.Body)
	}
	var e env
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil || e.Code != 0 {
		t.Fatalf("abort envelope = %s", rec.Body)
	}

	frames := collectUntil(t, ch, "session.idle")
	for _, f := range frames {
		if strings.Contains(f, "event: session.error") {
			t.Fatalf("abort 不应产生 session.error:\n%s", strings.Join(frames, "---\n"))
		}
	}
	// runs 表已清（consumeRun 收尾）
	deadline := time.Now().Add(2 * time.Second)
	for {
		h.mu.RLock()
		_, active := h.runs[cs.ID]
		h.mu.RUnlock()
		if !active {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("runs 表未清（consumeRun 未收尾）")
		}
		time.Sleep(10 * time.Millisecond)
	}
}

// TestAbortNoActiveRun：无进行中 turn 时 abort 幂等返回 aborted:true。
func TestAbortNoActiveRun(t *testing.T) {
	h := newChatTestHandler(t)
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_ddddddddddddddd1"}`)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/abort", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if !strings.Contains(rec.Body.String(), `"aborted":true`) {
		t.Fatalf("body = %s, want aborted:true", rec.Body)
	}
}
