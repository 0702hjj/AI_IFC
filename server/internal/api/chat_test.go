package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

func TestNewGlobalID(t *testing.T) {
	seen := map[string]bool{}
	for i := 0; i < 100; i++ {
		g := newGlobalID()
		if len(g) != 22 {
			t.Fatalf("len(%q) = %d, want 22", g, len(g))
		}
		if g[0] < '0' || g[0] > '3' {
			t.Fatalf("first char of %q must be 0-3", g)
		}
		for _, c := range g {
			if !strings.ContainsRune(ifcBase64Alphabet, c) {
				t.Fatalf("invalid char %c in %q", c, g)
			}
		}
		if seen[g] {
			t.Fatalf("duplicate guid %q", g)
		}
		seen[g] = true
	}
}

func TestModelIDFromEditedFile(t *testing.T) {
	cases := []struct {
		file string
		want string
	}{
		{"/data/uploads/m_cd21fae2ad2ae764.ifc", "m_cd21fae2ad2ae764"},
		{"/home/x/data/uploads/m_0517c9fce8b1827a.ifc", "m_0517c9fce8b1827a"},
		{"data/uploads/m_cd21fae2ad2ae764.ifc.new", ""}, // 临时文件不命中
		{"/data/staging/c_abc.ifc", ""},                 // 非 uploads 目录
		{"/data/uploads/not-a-model-id.ifc", ""},        // id 格式不符
		{"/data/uploads/m_CD21FAE2AD2AE764.ifc", ""},    // 大写不符
	}
	for _, c := range cases {
		if got := modelIDFromEditedFile(c.file); got != c.want {
			t.Errorf("modelIDFromEditedFile(%q) = %q, want %q", c.file, got, c.want)
		}
	}
}

// --- createSession 幂等与并发（会话连续性） ---

// newChatTestAgent 构造确定性 scripted agent + 事件日志（测试默认答复 "收到"）。
func newChatTestAgent(t *testing.T, dataDir string, script agent.Script) (*agent.Agent, *agent.EventStore) {
	t.Helper()
	st := agent.NewEventStore(dataDir)
	ag, err := agent.New(agent.LLMConfig{},
		agent.WithModel(agent.NewScriptedModel(script)),
		agent.WithStore(st),
	)
	if err != nil {
		t.Fatalf("agent.New: %v", err)
	}
	return ag, st
}

var defaultTestScript = agent.Script{Steps: []agent.ScriptStep{{Chunks: []string{"收到"}}}}

// newChatTestHandler 手动构造 ChatHandler（scripted agent），用于隔离测试 createSession/abort。
func newChatTestHandler(t *testing.T) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	ag, st := newChatTestAgent(t, dataDir, defaultTestScript)
	h := &ChatHandler{
		deps:     ChatDeps{Ag: ag, Ev: st, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// doChatCreate 直接调 createSession 并解 envelope，返回 session 或错误（goroutine 安全）。
func doChatCreate(h *ChatHandler, body string) (*chatSession, error) {
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions", strings.NewReader(body))
	rec := httptest.NewRecorder()
	h.createSession(rec, req)
	var e env
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil {
		return nil, fmt.Errorf("envelope decode: %w body=%s", err, rec.Body)
	}
	if e.Code != 0 {
		return nil, fmt.Errorf("envelope code=%d msg=%s", e.Code, e.Message)
	}
	var cs chatSession
	if err := json.Unmarshal(e.Data, &cs); err != nil {
		return nil, fmt.Errorf("session decode: %w data=%s", err, e.Data)
	}
	return &cs, nil
}

// TestLoadSessionsDedup 验证：同 modelId 多条 chatSession（竞态残留）加载时去重为最早一条，并写回文件。
func TestLoadSessionsDedup(t *testing.T) {
	h := newChatTestHandler(t)
	list := []*chatSession{
		{ID: "c_a", AgentID: "s_a", ModelID: "m_xxxxxxxxxxxxxxxx", Title: "t", CreatedAt: "2026-01-02T00:00:00Z"},
		{ID: "c_b", AgentID: "s_b", ModelID: "m_xxxxxxxxxxxxxxxx", Title: "t", CreatedAt: "2026-01-01T00:00:00Z"}, // 更早，应保留
		{ID: "c_c", AgentID: "s_c", ModelID: "m_yyyyyyyyyyyyyyyy", Title: "t", CreatedAt: "2026-01-03T00:00:00Z"},
	}
	data, _ := json.Marshal(list)
	if err := os.WriteFile(h.sessionsPath(), data, 0o644); err != nil {
		t.Fatal(err)
	}
	h.loadSessions()

	if got := len(h.sessions); got != 2 {
		t.Fatalf("去重后 sessions=%d, want 2（m_x 留 c_b、m_y 留 c_c）", got)
	}
	if _, ok := h.sessions["c_a"]; ok {
		t.Error("c_a（较晚）应被去重丢弃")
	}
	if _, ok := h.sessions["c_b"]; !ok {
		t.Error("c_b（最早）应保留")
	}
	if _, ok := h.byAgent["s_b"]; !ok {
		t.Error("byAgent 应含保留的 s_b")
	}

	// 文件应被写回去重
	var after []*chatSession
	data2, err := os.ReadFile(h.sessionsPath())
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data2, &after); err != nil {
		t.Fatal(err)
	}
	if len(after) != 2 {
		t.Fatalf("文件未写回去重: %d 条, want 2", len(after))
	}
}

// TestCreateSessionConcurrentIdempotent：同 modelId 并发 createSession（StrictMode dev 双发 /
// 用户连点）只产生一条会话——所有请求拿到同一 chatSessionId，映射表与持久化文件都只有一条。
func TestCreateSessionConcurrentIdempotent(t *testing.T) {
	h := newChatTestHandler(t)
	modelID := "m_aaaaaaaaaaaaaaaa"

	const N = 8
	results := make([]*chatSession, N)
	errs := make([]error, N)
	start := make(chan struct{})
	var wg sync.WaitGroup
	for i := 0; i < N; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			<-start // 同时放行，最大化 TOCTOU 竞态窗口
			body := `{"title":"t","modelId":"` + modelID + `"}`
			cs, err := doChatCreate(h, body)
			errs[i] = err
			results[i] = cs
		}(i)
	}
	close(start)
	wg.Wait()

	for i, err := range errs {
		if err != nil {
			t.Fatalf("goroutine[%d] error: %v", i, err)
		}
	}
	first := results[0].ID
	for i, cs := range results {
		if cs.ID != first {
			t.Fatalf("result[%d].ID = %q, want %q（同 modelId 会话连续性被破坏）", i, cs.ID, first)
		}
		if cs.AgentID == "" {
			t.Fatalf("result[%d].AgentID 为空（agent 会话 id 未分配）", i)
		}
	}
	h.mu.RLock()
	got := len(h.sessions)
	h.mu.RUnlock()
	if got != 1 {
		t.Fatalf("sessions map size = %d, want 1", got)
	}
	// 持久化文件同样只有一条
	var persisted []*chatSession
	data, err := os.ReadFile(h.sessionsPath())
	if err != nil {
		t.Fatal(err)
	}
	if err := json.Unmarshal(data, &persisted); err != nil {
		t.Fatal(err)
	}
	if len(persisted) != 1 {
		t.Fatalf("chat-sessions.json = %d 条, want 1（竞态未根治）", len(persisted))
	}
}

// TestArchiveStagingArtifact 验证构建脚本随版本归档到 models/{id}/scripts/，且 staging 源被清。
func TestArchiveStagingArtifact(t *testing.T) {
	h := newChatTestHandler(t)
	mid := "m_dddddddddddddddd"
	version := "v3"

	staging := filepath.Join(h.deps.DataDir, "staging")
	os.MkdirAll(staging, 0o755)
	os.WriteFile(filepath.Join(staging, mid+".py"), []byte("# build script"), 0o644)

	h.archiveStagingArtifact(mid, version, mid+".py", "scripts", "py")

	script := filepath.Join(h.deps.DataDir, "models", mid, "scripts", version+".py")
	if !fileExists(script) {
		t.Fatal("脚本未归档到 scripts/v3.py")
	}
	if fileExists(filepath.Join(staging, mid+".py")) {
		t.Fatal("归档后 staging 源文件应被删除")
	}

	// version 为空 → 跳过（不 panic、不归档）
	h.archiveStagingArtifact(mid, "", mid+".py", "scripts", "py")
	// 不存在的 staging 文件 → 跳过
	h.archiveStagingArtifact(mid, version, mid+".absent", "absent", "x")
}

// TestAbortSessionNotFound 测不存在的 cid → 404。
func TestAbortSessionNotFound(t *testing.T) {
	h := newChatTestHandler(t)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/c_nope/abort", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d, want 404", rec.Code)
	}
}

// --- createProject 路径（P0-3：与前端 /api/v1/chat/projects 对齐） ---

// newChatProjectTestHandler 构造带 store + 转换队列的 chat handler（createProject 依赖）。
func newChatProjectTestHandler(t *testing.T) *ChatHandler {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	q := convert.NewQueue(st, okRunner{}, 1)
	h := &ChatHandler{
		deps:     ChatDeps{St: st, Ps: store.NewProjectStore(dataDir), Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// TestCreateProjectViaChatPath 断言 POST /api/v1/chat/projects 经 chat mux 可达：
// 200 + envelope + 空白项目创建（projectId + 空 models，不产模型）。
func TestCreateProjectViaChatPath(t *testing.T) {
	h := newChatProjectTestHandler(t)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/projects", strings.NewReader(`{"title":"我的项目","kind":"cad"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s, want 200（chat mux 未注册 /api/v1/chat/projects）", rec.Code, rec.Body)
	}
	var e env
	if err := json.Unmarshal(rec.Body.Bytes(), &e); err != nil {
		t.Fatalf("envelope decode: %v body=%s", err, rec.Body)
	}
	if e.Code != 0 {
		t.Fatalf("envelope code=%d msg=%s, want 0", e.Code, e.Message)
	}
	var r struct {
		ProjectID string `json:"projectId"`
		Models    int    `json:"-"`
	}
	if err := json.Unmarshal(e.Data, &r); err != nil {
		t.Fatalf("project decode: %v data=%s", err, e.Data)
	}
	if !strings.HasPrefix(r.ProjectID, "p_") || len(r.ProjectID) != 18 {
		t.Errorf("projectId %q 不符合 p_ + 16 hex", r.ProjectID)
	}
	// 不产模型（store 空）
	if ms, _ := h.deps.St.List(); len(ms) != 0 {
		t.Errorf("空白项目不应注册模型: %+v", ms)
	}
}

// waitModelStatus 轮询模型状态直到期望值或超时（条件等待，不用固定 sleep）。
func waitModelStatus(t *testing.T, st *store.Store, id, want string, timeout time.Duration) {
	t.Helper()
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		m, err := st.Get(id)
		if err == nil && m.Status == want {
			return
		}
		time.Sleep(10 * time.Millisecond)
	}
	m, err := st.Get(id)
	if err != nil {
		t.Fatalf("等待状态 %q 期间读取模型失败: %v", want, err)
	}
	t.Fatalf("等待模型 %s 状态 %q 超时（当前 %q）", id, want, m.Status)
}

// TestCreateProjectOldPathGone 断言旧路径 POST /api/v1/projects 不再由 chat mux 处理（404）。
func TestCreateProjectOldPathGone(t *testing.T) {
	h := newChatProjectTestHandler(t)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/projects", strings.NewReader(`{"title":"t"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d body = %s, want 404（旧路径 /api/v1/projects 应已移除）", rec.Code, rec.Body)
	}
}

// TestCreateSessionSerialReuse 验证串行幂等：先建一次，再用同 modelId 建第二次直接复用第一条。
func TestCreateSessionSerialReuse(t *testing.T) {
	h := newChatTestHandler(t)
	modelID := "m_bbbbbbbbbbbbbbbb"

	cs1, err := doChatCreate(h, `{"title":"t","modelId":"`+modelID+`"}`)
	if err != nil {
		t.Fatal(err)
	}
	cs2, err := doChatCreate(h, `{"title":"t","modelId":"`+modelID+`"}`)
	if err != nil {
		t.Fatal(err)
	}
	if cs1.ID != cs2.ID || cs1.AgentID != cs2.AgentID {
		t.Fatalf("serial reuse: cs1=%+v cs2=%+v, want same id+agentId", cs1, cs2)
	}
}
