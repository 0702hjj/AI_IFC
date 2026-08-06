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
	"sync/atomic"
	"testing"
	"time"

	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/opencode"
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
		{"/home/x/viewer/data/uploads/m_0517c9fce8b1827a.ifc", "m_0517c9fce8b1827a"},
		{"viewer/data/uploads/m_cd21fae2ad2ae764.ifc.new", ""}, // 临时文件不命中
		{"/data/staging/c_abc.ifc", ""},                        // 非 uploads 目录
		{"/data/uploads/not-a-model-id.ifc", ""},               // id 格式不符
		{"/data/uploads/m_CD21FAE2AD2AE764.ifc", ""},           // 大写不符
	}
	for _, c := range cases {
		if got := modelIDFromEditedFile(c.file); got != c.want {
			t.Errorf("modelIDFromEditedFile(%q) = %q, want %q", c.file, got, c.want)
		}
	}
}

func TestIfcProjectGUID(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.ifc")
	content := `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1=IFCPROJECT('2SdOxgmHH1hB$6KI7DupXo',#2,'Smoke',$,$,$,$,(#8),#9);
#2=IFCOWNERHISTORY($,$,$,$,$,$,$,$);
ENDSEC;
END-ISO-10303-21;
`
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	guid, err := ifcProjectGUID(path)
	if err != nil {
		t.Fatal(err)
	}
	if guid != "2SdOxgmHH1hB$6KI7DupXo" {
		t.Errorf("guid = %q", guid)
	}

	empty := filepath.Join(dir, "empty.ifc")
	if err := os.WriteFile(empty, []byte("DATA;\nENDSEC;"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := ifcProjectGUID(empty); err == nil {
		t.Error("expected error for file without IFCPROJECT")
	}
}

// --- createSession 幂等与并发（会话连续性） ---

// newChatTestHandler 手动构造 ChatHandler（不启动 dispatchLoop），用于隔离测试 createSession/abort。
func newChatTestHandler(t *testing.T, ocURL string) *ChatHandler {
	t.Helper()
	h := &ChatHandler{
		deps:     ChatDeps{OC: opencode.New(ocURL), DataDir: t.TempDir()},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byOC:     map[string]string{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// fakeOC 起一个记录 POST /session 调用次数的假 opencode serve。
// abortCnt（非 nil 时）记录 POST /session/{id}/abort 次数，用于测中止转发。
func fakeOC(t *testing.T, createCount *int32) *httptest.Server {
	t.Helper()
	return fakeOCWithAbort(t, createCount, nil)
}

func fakeOCWithAbort(t *testing.T, createCount *int32, abortCnt *int32) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodPost && r.URL.Path == "/session" {
			n := atomic.AddInt32(createCount, 1)
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprintf(w, `{"id":"oc_%d","title":"t"}`, n)
			return
		}
		if r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/abort") && abortCnt != nil {
			atomic.AddInt32(abortCnt, 1)
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	t.Cleanup(srv.Close)
	return srv
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
	var createCount int32
	srv := fakeOC(t, &createCount)
	h := newChatTestHandler(t, srv.URL)
	list := []*chatSession{
		{ID: "c_a", OpencodeID: "oc_a", ModelID: "m_xxxxxxxxxxxxxxxx", Title: "t", CreatedAt: "2026-01-02T00:00:00Z"},
		{ID: "c_b", OpencodeID: "oc_b", ModelID: "m_xxxxxxxxxxxxxxxx", Title: "t", CreatedAt: "2026-01-01T00:00:00Z"}, // 更早，应保留
		{ID: "c_c", OpencodeID: "oc_c", ModelID: "m_yyyyyyyyyyyyyyyy", Title: "t", CreatedAt: "2026-01-03T00:00:00Z"},
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
	if _, ok := h.byOC["oc_b"]; !ok {
		t.Error("byOC 应含保留的 oc_b")
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
// 只产生一条会话（只调一次 opencode CreateSession，所有请求拿到同一 chatSessionId）。
// 复现场景：React StrictMode 下 ViewerPage effect 连发两次 createChatSession。
func TestCreateSessionConcurrentIdempotent(t *testing.T) {
	var createCount int32
	srv := fakeOC(t, &createCount)
	h := newChatTestHandler(t, srv.URL)
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
	if createCount != 1 {
		t.Fatalf("opencode CreateSession called %d times, want 1（竞态未根治：StrictMode 双发会建多条会话）", createCount)
	}
	first := results[0].ID
	for i, cs := range results {
		if cs.ID != first {
			t.Fatalf("result[%d].ID = %q, want %q（同 modelId 会话连续性被破坏）", i, cs.ID, first)
		}
	}
	h.mu.RLock()
	got := len(h.sessions)
	h.mu.RUnlock()
	if got != 1 {
		t.Fatalf("sessions map size = %d, want 1", got)
	}
}

// TestArchiveStagingArtifact 验证脚本 + design.json 两个制品都随版本归档到 models/{id}/，且 staging 源被清。
func TestArchiveStagingArtifact(t *testing.T) {
	var createCount int32
	srv := fakeOC(t, &createCount)
	h := newChatTestHandler(t, srv.URL)
	mid := "m_dddddddddddddddd"
	version := "v3"

	staging := filepath.Join(h.deps.DataDir, "staging")
	os.MkdirAll(staging, 0o755)
	os.WriteFile(filepath.Join(staging, mid+".py"), []byte("# build script"), 0o644)
	os.WriteFile(filepath.Join(staging, mid+".design.json"), []byte(`{"meta":{}}`), 0o644)

	h.archiveStagingArtifact(mid, version, mid+".py", "scripts", "py")
	h.archiveStagingArtifact(mid, version, mid+".design.json", "designs", "json")

	script := filepath.Join(h.deps.DataDir, "models", mid, "scripts", version+".py")
	design := filepath.Join(h.deps.DataDir, "models", mid, "designs", version+".json")
	if !fileExists(script) {
		t.Fatal("脚本未归档到 scripts/v3.py")
	}
	if !fileExists(design) {
		t.Fatal("design.json 未归档到 designs/v3.json")
	}
	if fileExists(filepath.Join(staging, mid+".py")) || fileExists(filepath.Join(staging, mid+".design.json")) {
		t.Fatal("归档后 staging 源文件应被删除")
	}

	// version 为空 → 跳过（不 panic、不归档）
	h.archiveStagingArtifact(mid, "", mid+".py", "scripts", "py")
	// 不存在的 staging 文件 → 跳过
	h.archiveStagingArtifact(mid, version, mid+".absent", "absent", "x")
}
func TestAbortSessionForwards(t *testing.T) {
	var createCount, abortCnt int32
	srv := fakeOCWithAbort(t, &createCount, &abortCnt)
	h := newChatTestHandler(t, srv.URL)
	// 建一条会话拿到 chatSessionId
	cs, err := doChatCreate(h, `{"title":"t","modelId":"m_cccccccccccccccc"}`)
	if err != nil {
		t.Fatal(err)
	}
	// 经 mux 打 abort（走真实路由 + path value）
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/abort", nil)
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body)
	}
	if abortCnt != 1 {
		t.Fatalf("opencode abort called %d times, want 1", abortCnt)
	}
}

// TestAbortSessionNotFound 测不存在的 cid → 404。
func TestAbortSessionNotFound(t *testing.T) {
	var createCount int32
	srv := fakeOC(t, &createCount)
	h := newChatTestHandler(t, srv.URL)
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
		deps:     ChatDeps{St: st, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byOC:     map[string]string{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	return h
}

// TestCreateProjectViaChatPath 断言 POST /api/v1/chat/projects 经 chat mux 可达：
// 200 + envelope + 返回 ModelInfo（骨架 IFC 落盘 + 入队转换）。
func TestCreateProjectViaChatPath(t *testing.T) {
	h := newChatProjectTestHandler(t)
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/projects", strings.NewReader(`{"title":"我的项目"}`))
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
	var m store.Model
	if err := json.Unmarshal(e.Data, &m); err != nil {
		t.Fatalf("model decode: %v data=%s", err, e.Data)
	}
	if !modelIDRe.MatchString(m.ID) {
		t.Errorf("model id %q 不符合 ^m_[0-9a-f]{16}$", m.ID)
	}
	if m.Name != "我的项目.ifc" {
		t.Errorf("model name = %q, want 我的项目.ifc", m.Name)
	}
	content, err := os.ReadFile(filepath.Join(h.deps.DataDir, "uploads", m.ID+".ifc"))
	if err != nil {
		t.Fatalf("骨架 IFC 未落盘: %v", err)
	}
	if !strings.Contains(string(content), "IFCPROJECT") || !strings.Contains(string(content), "我的项目") {
		t.Errorf("骨架 IFC 内容不符: %s", content)
	}
	// 转换是异步的（Queue worker 会写 models/{id}/model.json），
	// 必须等其完成再结束测试，否则 TempDir 清理与 worker 写盘竞争（flaky）。
	waitModelStatus(t, h.deps.St, m.ID, "ready", 5*time.Second)
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
	var createCount int32
	srv := fakeOC(t, &createCount)
	h := newChatTestHandler(t, srv.URL)
	modelID := "m_bbbbbbbbbbbbbbbb"

	cs1, err := doChatCreate(h, `{"title":"t","modelId":"`+modelID+`"}`)
	if err != nil {
		t.Fatal(err)
	}
	cs2, err := doChatCreate(h, `{"title":"t","modelId":"`+modelID+`"}`)
	if err != nil {
		t.Fatal(err)
	}
	if cs1.ID != cs2.ID || cs1.OpencodeID != cs2.OpencodeID {
		t.Fatalf("serial reuse: cs1=%+v cs2=%+v, want same id+opencodeId", cs1, cs2)
	}
	if createCount != 1 {
		t.Fatalf("CreateSession called %d times, want 1", createCount)
	}
}
