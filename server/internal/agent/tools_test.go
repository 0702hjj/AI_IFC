// tools_test.go：领域工具测试夹具（fakeBackend/newToolFixture/invoke/mustModel）
// + 注册面与正常路径代理测试；错误/kind 路由/守卫见 tools_guard_test.go，
// run_script 中途预览见 tools_staged_test.go，agent 集成见 tools_integration_test.go。
package agent

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/components/tool/utils"

	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// newStringTool 包一个无参文本工具（agent 集成测试用）。
func newStringTool(name string, fn func(ctx context.Context) (string, error)) (tool.BaseTool, error) {
	return utils.InferTool(name, name, func(ctx context.Context, _ emptyReq) (string, error) {
		return fn(ctx)
	})
}

// --- 测试夹具 ---

type recordedReq struct {
	method string
	path   string
	body   string
}

// fakeBackend 记录全部请求并按固定响应应答（kind 路由双 fake 钉死用）。
type fakeBackend struct {
	mu     sync.Mutex
	reqs   []recordedReq
	status int
	body   string
}

func newFakeBackend(t *testing.T, status int, body string) (*fakeBackend, *editsvc.Client) {
	t.Helper()
	fb := &fakeBackend{status: status, body: body}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		fb.mu.Lock()
		fb.reqs = append(fb.reqs, recordedReq{method: r.Method, path: r.URL.Path, body: string(b)})
		fb.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(fb.status)
		_, _ = io.WriteString(w, fb.body)
	}))
	t.Cleanup(srv.Close)
	return fb, editsvc.New(srv.URL)
}

func (fb *fakeBackend) count() int {
	fb.mu.Lock()
	defer fb.mu.Unlock()
	return len(fb.reqs)
}

// saw 断言记录中出现过一次指定 method+path 的请求（run_script 成功后会追加
// staging diff 轻量调用，last() 不再恒为工具主调用——改用 saw 钉主调用发生过）。
func (fb *fakeBackend) saw(method, path string) bool {
	fb.mu.Lock()
	defer fb.mu.Unlock()
	for _, r := range fb.reqs {
		if r.method == method && r.path == path {
			return true
		}
	}
	return false
}

func (fb *fakeBackend) last() recordedReq {
	fb.mu.Lock()
	defer fb.mu.Unlock()
	if len(fb.reqs) == 0 {
		return recordedReq{}
	}
	return fb.reqs[len(fb.reqs)-1]
}

// newToolFixture 造双后端 fake + 空 store 的 ToolDeps（SessionModel/MarkDirty/CreateProject 按需覆盖）。
func newToolFixture(t *testing.T) (ToolDeps, *fakeBackend, *fakeBackend, *store.Store) {
	t.Helper()
	ifcFB, ifcCl := newFakeBackend(t, http.StatusOK, `{"ok":true}`)
	cadFB, cadCl := newFakeBackend(t, http.StatusOK, `{"ok":true}`)
	st := store.NewStore(t.TempDir())
	return ToolDeps{IFC: ifcCl, CAD: cadCl, St: st}, ifcFB, cadFB, st
}

func toolNames(tools []tool.InvokableTool) []string {
	var names []string
	for _, tl := range tools {
		info, err := tl.Info(context.Background())
		if err != nil {
			continue
		}
		names = append(names, info.Name)
	}
	return names
}

// invoke 直接以 JSON 参数调用工具（等同模型 tool_call 路径），返回文本结果。
func invoke(t *testing.T, tools []tool.InvokableTool, name, args string) string {
	t.Helper()
	return invokeCtx(t, tools, context.Background(), name, args)
}

func invokeCtx(t *testing.T, tools []tool.InvokableTool, ctx context.Context, name, args string) string {
	t.Helper()
	for _, tl := range tools {
		info, err := tl.Info(ctx)
		if err != nil || info.Name != name {
			continue
		}
		out, err := tl.InvokableRun(ctx, args)
		if err != nil {
			t.Fatalf("工具 %s 返回 Go error（应错误文本化）: %v", name, err)
		}
		return out
	}
	t.Fatalf("工具 %s 未注册（已有 %v）", name, toolNames(tools))
	return ""
}

func mustModel(t *testing.T, st *store.Store, name, kind string) *store.Model {
	t.Helper()
	m, err := st.CreateWithKind(name, 4, strings.NewReader("fake"), kind)
	if err != nil {
		t.Fatalf("create %s model: %v", kind, err)
	}
	return m
}

// --- 注册面 ---

func TestDomainToolsRegistered(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	got := toolNames(DomainTools(deps))
	want := []string{
		"list_models", "get_model_info", "get_script", "stage_script", "run_script",
		"save_script", "get_versions", "get_diff", "create_project",
	}
	if len(got) != len(want) {
		t.Fatalf("工具数 = %d (%v), want %d (%v)", len(got), got, len(want), want)
	}
	seen := map[string]bool{}
	for _, n := range got {
		seen[n] = true
	}
	for _, w := range want {
		if !seen[w] {
			t.Fatalf("缺工具 %s（已有 %v）", w, got)
		}
	}
}

// --- 正常路径 ---

func TestListModelsCarriesKind(t *testing.T) {
	deps, _, _, st := newToolFixture(t)
	mi := mustModel(t, st, "a.ifc", store.KindIFC)
	md := mustModel(t, st, "b.dxf", store.KindDXF)
	out := invoke(t, DomainTools(deps), "list_models", `{}`)
	var models []map[string]any
	if err := json.Unmarshal([]byte(out), &models); err != nil {
		t.Fatalf("list_models 输出非 JSON 数组: %v\n%s", err, out)
	}
	kinds := map[string]string{}
	for _, m := range models {
		id, _ := m["id"].(string)
		kind, _ := m["kind"].(string)
		kinds[id] = kind
	}
	if kinds[mi.ID] != "ifc" || kinds[md.ID] != "dxf" {
		t.Fatalf("kind 未带出: %v", kinds)
	}
}

func TestGetModelInfo(t *testing.T) {
	deps, _, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "get_model_info", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, m.ID) || !strings.Contains(out, `"kind":"ifc"`) {
		t.Fatalf("get_model_info 输出缺 id/kind: %s", out)
	}
}

func TestGetScriptProxies(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "get_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("get_script 输出 = %s", out)
	}
	last := ifcFB.last()
	if last.method != http.MethodGet || last.path != "/models/"+m.ID+"/script" {
		t.Fatalf("后端收到 %s %s, want GET /models/%s/script", last.method, last.path, m.ID)
	}
}

func TestStageScriptPutsBodyAndMarksDirty(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	var dirty bool
	deps.MarkDirty = func(ctx context.Context) { dirty = true }
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "stage_script",
		`{"modelId":"`+m.ID+`","script":"print(1)","note":"加墙"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("stage_script 输出 = %s", out)
	}
	last := ifcFB.last()
	if last.method != http.MethodPut || last.path != "/models/"+m.ID+"/script" {
		t.Fatalf("后端收到 %s %s, want PUT /models/%s/script", last.method, last.path, m.ID)
	}
	var body map[string]any
	if err := json.Unmarshal([]byte(last.body), &body); err != nil {
		t.Fatalf("PUT body 非 JSON: %s", last.body)
	}
	if body["script"] != "print(1)" {
		t.Fatalf("PUT body script = %v", body["script"])
	}
	if !dirty {
		t.Fatal("stage_script 成功后应标记会话 dirty")
	}
}

func TestRunScriptUsesSlowPathAndMarksDirty(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	var dirty bool
	deps.MarkDirty = func(ctx context.Context) { dirty = true }
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("run_script 输出 = %s", out)
	}
	if !ifcFB.saw(http.MethodPost, "/models/"+m.ID+"/script/run") {
		t.Fatalf("后端未收到 POST /models/%s/script/run", m.ID)
	}
	if !dirty {
		t.Fatal("run_script 成功后应标记会话 dirty")
	}
}

func TestSaveScriptPostsNoteAndMarksDirty(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	var dirty bool
	deps.MarkDirty = func(ctx context.Context) { dirty = true }
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "save_script", `{"modelId":"`+m.ID+`","note":"v1 收工"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("save_script 输出 = %s", out)
	}
	last := ifcFB.last()
	if last.method != http.MethodPost || last.path != "/models/"+m.ID+"/script/save" {
		t.Fatalf("后端收到 %s %s, want POST /models/%s/script/save", last.method, last.path, m.ID)
	}
	if !strings.Contains(last.body, "v1 收工") {
		t.Fatalf("save body 缺 note: %s", last.body)
	}
	if !dirty {
		t.Fatal("save_script 成功后应标记会话 dirty")
	}
}

func TestGetVersionsProxiesScripts(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "get_versions", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("get_versions 输出 = %s", out)
	}
	last := ifcFB.last()
	if last.method != http.MethodGet || last.path != "/models/"+m.ID+"/scripts" {
		t.Fatalf("后端收到 %s %s, want GET /models/%s/scripts", last.method, last.path, m.ID)
	}
}

func TestGetDiffPostsBaseTarget(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	out := invoke(t, DomainTools(deps), "get_diff",
		`{"modelId":"`+m.ID+`","base":"v1","target":"v2"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("get_diff 输出 = %s", out)
	}
	last := ifcFB.last()
	if last.method != http.MethodPost || last.path != "/models/"+m.ID+"/script/diff" {
		t.Fatalf("后端收到 %s %s, want POST /models/%s/script/diff", last.method, last.path, m.ID)
	}
	var body map[string]any
	if err := json.Unmarshal([]byte(last.body), &body); err != nil {
		t.Fatalf("diff body 非 JSON: %s", last.body)
	}
	if body["base"] != "v1" || body["target"] != "v2" {
		t.Fatalf("diff body = %v", body)
	}
}

// TestCreateProjectInvokesDepNoDirty：create_project 调 CreateProject 返回新模型，
// 但不置会话 dirty——新模型 B ≠ 会话绑定模型 A，置位会让 notify 对未变更的 A
// 跑完整管线（错绑，评审修复 round 1）。
func TestCreateProjectInvokesDepNoDirty(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	var gotTitle string
	var dirty bool
	deps.MarkDirty = func(ctx context.Context) { dirty = true }
	deps.CreateProject = func(ctx context.Context, title string) (any, error) {
		gotTitle = title
		return map[string]any{"id": "m_1111111111111111", "name": title + ".ifc"}, nil
	}
	out := invoke(t, DomainTools(deps), "create_project", `{"title":"商场"}`)
	if gotTitle != "商场" {
		t.Fatalf("CreateProject title = %q", gotTitle)
	}
	if !strings.Contains(out, "m_1111111111111111") {
		t.Fatalf("create_project 输出应带新模型 id: %s", out)
	}
	if dirty {
		t.Fatal("create_project 不应标记会话 dirty（防 notify 对绑定模型错跑管线）")
	}
}
