package api

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/editsvc"
)

// --- W-0016：会话消息注入「与上一大版本的脚本 diff」上下文 ---

// newChatTestHandlerWithEd 构造带 edit-service 客户端的 chat 测试 handler。
func newChatTestHandlerWithEd(t *testing.T, edURL string) *ChatHandler {
	t.Helper()
	h := newChatTestHandler(t)
	if edURL != "" {
		h.deps.Ed = editsvc.New(edURL)
	}
	return h
}

// fakeEditSvc 假 edit-service：按路径回 scripts 列表 / script diff（其余 404）。
func fakeEditSvc(t *testing.T, scripts []map[string]any, diff map[string]any) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/scripts") {
			_ = json.NewEncoder(w).Encode(map[string]any{
				"modelId": "m_x", "scripts": scripts, "versions": []any{},
			})
			return
		}
		if r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/script/diff") && diff != nil {
			_ = json.NewEncoder(w).Encode(diff)
			return
		}
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(map[string]any{"detail": "not found"})
	}))
	t.Cleanup(srv.Close)
	return srv
}

func twoScripts() []map[string]any {
	return []map[string]any{
		{"version": "v1", "createdAt": "2026-08-06T00:00:00Z", "note": ""},
		{"version": "v2", "createdAt": "2026-08-07T00:00:00Z", "note": ""},
	}
}

func smallDiff() map[string]any {
	return map[string]any{
		"base":      "v1",
		"target":    "v2",
		"text_diff": "--- v1\n+++ v2\n@@ -1,1 +1,1 @@\n-PARAMS = {\"width\": 3}\n+PARAMS = {\"width\": 5}\n",
		"params_changes": []map[string]any{
			{"key": "width", "action": "modified", "old": 3, "new": 5},
		},
		"stats": map[string]any{"added": 1, "removed": 1},
	}
}

// TestScriptDiffContextTwoVersions：≥2 个大版本时注入最近两个大版本的 diff + PARAMS 摘要 + 纪律提示。
func TestScriptDiffContextTwoVersions(t *testing.T) {
	ed := fakeEditSvc(t, twoScripts(), smallDiff())
	h := newChatTestHandlerWithEd(t, ed.URL)

	got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa")
	if got == "" {
		t.Fatal("两个大版本时应产出 diff 上下文")
	}
	for _, want := range []string{
		"v1", "v2", // 标注 base → target
		`+PARAMS = {"width": 5}`, // 全量 unified diff 原文
		"width", "3", "5",        // PARAMS 变化摘要
		"增量修改", "重写", "key", // 纪律提示
	} {
		if !strings.Contains(got, want) {
			t.Errorf("注入上下文缺少 %q:\n%s", want, got)
		}
	}
}

// TestScriptDiffContextTruncated：text_diff 超 4KB 时只给 stats + params_changes 摘要，不含全量文本。
func TestScriptDiffContextTruncated(t *testing.T) {
	big := strings.Repeat("+line_of_code_x\n", 400) // 7200 字节 > 4KB
	diff := smallDiff()
	diff["text_diff"] = big
	diff["stats"] = map[string]any{"added": 400, "removed": 0}
	ed := fakeEditSvc(t, twoScripts(), diff)
	h := newChatTestHandlerWithEd(t, ed.URL)

	got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa")
	if got == "" {
		t.Fatal("超长 diff 也应产出摘要上下文")
	}
	if strings.Contains(got, strings.Repeat("+line_of_code_x\n", 10)) {
		t.Error("超长 diff 不应注入全量文本")
	}
	if !strings.Contains(got, "400") {
		t.Errorf("摘要应含 stats 行数:\n%s", got)
	}
	if !strings.Contains(got, "width") {
		t.Errorf("摘要应含 PARAMS 变化:\n%s", got)
	}
	if !strings.Contains(got, "增量修改") {
		t.Errorf("摘要也应含纪律提示:\n%s", got)
	}
	if len(got) > 4096 {
		t.Errorf("摘要上下文自身不应超长: %d bytes", len(got))
	}
}

// TestScriptDiffContextFallback：无脚本/单版本/不可达/无 Ed 客户端 → 返回 ""（不注入、不报错）。
func TestScriptDiffContextFallback(t *testing.T) {
	// 单大版本 → ""
	ed1 := fakeEditSvc(t, twoScripts()[:1], smallDiff())
	h := newChatTestHandlerWithEd(t, ed1.URL)
	if got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa"); got != "" {
		t.Errorf("单大版本不应注入 diff, got %q", got)
	}

	// 无脚本（legacy IFC 模型）→ ""
	ed0 := fakeEditSvc(t, []map[string]any{}, smallDiff())
	h = newChatTestHandlerWithEd(t, ed0.URL)
	if got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa"); got != "" {
		t.Errorf("无脚本模型不应注入 diff, got %q", got)
	}

	// edit-service 不可达（连接被拒，快速失败）→ ""
	h = newChatTestHandlerWithEd(t, "http://127.0.0.1:1")
	if got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa"); got != "" {
		t.Errorf("edit-service 不可达应降级为空, got %q", got)
	}

	// Ed 为 nil（chat 测试 handler 默认形态）→ ""
	h = newChatTestHandler(t)
	if got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa"); got != "" {
		t.Errorf("无 Ed 客户端应返回空, got %q", got)
	}

	// diff 端点本身报错（scripts 列表正常）→ ""
	edBad := fakeEditSvc(t, twoScripts(), nil)
	h = newChatTestHandlerWithEd(t, edBad.URL)
	if got := h.scriptDiffContext(context.Background(), "m_aaaaaaaaaaaaaaaa"); got != "" {
		t.Errorf("diff 拉取失败应降级为空, got %q", got)
	}
}

// spyModel 捕获 agent 收到的用户文本（postMessage 注入系统上下文后的完整 prompt）。
type spyModel struct {
	mu   sync.Mutex
	last string
}

func (m *spyModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	return m, nil
}

func (m *spyModel) record(input []*schema.Message) {
	m.mu.Lock()
	defer m.mu.Unlock()
	for _, msg := range input {
		if msg.Role == schema.User {
			m.last = msg.Content
		}
	}
}

func (m *spyModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	m.record(input)
	return &schema.Message{Role: schema.Assistant, Content: "收到"}, nil
}

func (m *spyModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	m.record(input)
	return schema.StreamReaderFromArray([]*schema.Message{{Role: schema.Assistant, Content: "收到"}}), nil
}

func (m *spyModel) captured() string {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.last
}

// newSpyChatHandler 构造 agent 为 spyModel 的 chat 测试 handler（Ed 可选）。
func newSpyChatHandler(t *testing.T, spy *spyModel, edURL string) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	st := agent.NewEventStore(dataDir)
	ag, err := agent.New(agent.LLMConfig{}, agent.WithModel(spy), agent.WithStore(st))
	if err != nil {
		t.Fatalf("agent.New: %v", err)
	}
	h := newChatTestHandler(t)
	h.deps.DataDir = dataDir
	h.deps.Ag = ag
	h.deps.Ev = st
	if edURL != "" {
		h.deps.Ed = editsvc.New(edURL)
	}
	return h
}

// capturedPrompt 条件等待 spyModel 收到 prompt（postMessage 的 agent 运行是异步的），超时即失败。
func capturedPrompt(t *testing.T, spy *spyModel) string {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for time.Now().Before(deadline) {
		if s := spy.captured(); s != "" {
			return s
		}
		time.Sleep(10 * time.Millisecond)
	}
	t.Fatal("agent 未收到 prompt")
	return ""
}

// TestPostMessageInjectsScriptDiff：端到端——绑定有两个大版本的模型，下发消息含 diff 上下文。
func TestPostMessageInjectsScriptDiff(t *testing.T) {
	spy := &spyModel{}
	ed := fakeEditSvc(t, twoScripts(), smallDiff())
	h := newSpyChatHandler(t, spy, ed.URL)
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_aaaaaaaaaaaaaaaa"}`)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/messages", strings.NewReader(`{"text":"把宽度改成 6"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	got := capturedPrompt(t, spy)
	for _, want := range []string{
		"[系统上下文]", "data/uploads/m_aaaaaaaaaaaaaaaa.ifc",
		`+PARAMS = {"width": 5}`, "增量修改", "[用户需求] 把宽度改成 6",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("prompt 缺少 %q:\n%s", want, got)
		}
	}
}

// TestPostMessageNoScriptKeepsLegacyContext：无脚本模型保持现行为（只注入模型路径，无 diff/纪律段）。
func TestPostMessageNoScriptKeepsLegacyContext(t *testing.T) {
	spy := &spyModel{}
	ed := fakeEditSvc(t, []map[string]any{}, smallDiff())
	h := newSpyChatHandler(t, spy, ed.URL)
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_bbbbbbbbbbbbbbbb"}`)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/messages", strings.NewReader(`{"text":"hi"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	got := capturedPrompt(t, spy)
	if !strings.Contains(got, "data/uploads/m_bbbbbbbbbbbbbbbb.ifc") || !strings.Contains(got, "[用户需求] hi") {
		t.Errorf("应保留现有系统上下文格式:\n%s", got)
	}
	if strings.Contains(got, "增量修改") || strings.Contains(got, "```diff") {
		t.Errorf("无脚本模型不应注入 diff 段:\n%s", got)
	}
}

// TestPostMessageEditSvcDownStillSends：edit-service 不可达时消息照常下发（降级不阻塞）。
func TestPostMessageEditSvcDownStillSends(t *testing.T) {
	spy := &spyModel{}
	h := newSpyChatHandler(t, spy, "http://127.0.0.1:1")
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_cccccccccccccccc"}`)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/messages", strings.NewReader(`{"text":"hi"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("edit-service 不可达不应阻塞消息: status = %d body = %s", rec.Code, rec.Body)
	}
	got := capturedPrompt(t, spy)
	if !strings.Contains(got, "[用户需求] hi") {
		t.Errorf("消息应照常下发:\n%s", got)
	}
	if strings.Contains(got, "增量修改") {
		t.Errorf("不可达时不应注入 diff 段:\n%s", got)
	}
}
