package agent

import (
	"context"
	"encoding/json"
	"errors"
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
	last := ifcFB.last()
	if last.method != http.MethodPost || last.path != "/models/"+m.ID+"/script/run" {
		t.Fatalf("后端收到 %s %s, want POST /models/%s/script/run", last.method, last.path, m.ID)
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

func TestCreateProjectInvokesDepAndMarksDirty(t *testing.T) {
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
	if !dirty {
		t.Fatal("create_project 成功后应标记会话 dirty")
	}
}

// --- 错误文本化 / 截断 ---

func TestToolErrorTextualized(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	ifcFB.status = http.StatusUnprocessableEntity
	ifcFB.body = `{"detail":"脚本第 3 行语法错误"}`
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, "调用失败") || !strings.Contains(out, "脚本第 3 行语法错误") {
		t.Fatalf("错误未文本化（LLM 无法观测）: %s", out)
	}
}

func TestToolResultTruncatedAt64K(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	ifcFB.body = `{"script":"` + strings.Repeat("x", 200000) + `"}`
	out := invoke(t, DomainTools(deps), "get_script", `{"modelId":"`+m.ID+`"}`)
	if len(out) > maxToolResult+64 {
		t.Fatalf("输出未截断: len=%d", len(out))
	}
	if !strings.Contains(out, "(truncated)") {
		t.Fatalf("输出缺截断标记: ...%s", out[len(out)-40:])
	}
}

// --- kind 路由（双 fake 钉死） ---

func TestKindRoutingDXFGoesToCadOnly(t *testing.T) {
	deps, ifcFB, cadFB, st := newToolFixture(t)
	m := mustModel(t, st, "plan.dxf", store.KindDXF)
	invoke(t, DomainTools(deps), "get_script", `{"modelId":"`+m.ID+`"}`)
	if cadFB.count() != 1 {
		t.Fatalf("cad 后端命中 = %d, want 1", cadFB.count())
	}
	if ifcFB.count() != 0 {
		t.Fatalf("ifc 后端命中 = %d, want 0（dxf 模型不得打到 :8100）", ifcFB.count())
	}
}

func TestKindRoutingIFCGoesToIfcOnly(t *testing.T) {
	deps, ifcFB, cadFB, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if ifcFB.count() != 1 {
		t.Fatalf("ifc 后端命中 = %d, want 1", ifcFB.count())
	}
	if cadFB.count() != 0 {
		t.Fatalf("cad 后端命中 = %d, want 0", cadFB.count())
	}
}

// --- 守卫 ---

func TestUnknownModelIDTextualizedNoBackendHit(t *testing.T) {
	deps, ifcFB, cadFB, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "get_script", `{"modelId":"m_0000000000000000"}`)
	if !strings.Contains(out, "m_0000000000000000") {
		t.Fatalf("未知 modelId 应错误文本化: %s", out)
	}
	if ifcFB.count()+cadFB.count() != 0 {
		t.Fatal("守卫失败：未知 modelId 不应触达任何后端")
	}
}

func TestInvalidModelIDRejectedNoBackendHit(t *testing.T) {
	deps, ifcFB, cadFB, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "get_script", `{"modelId":"../../etc/passwd"}`)
	if out == "" || strings.Contains(out, `"ok":true`) {
		t.Fatalf("非法 modelId 应拒绝: %s", out)
	}
	if ifcFB.count()+cadFB.count() != 0 {
		t.Fatal("守卫失败：非法 modelId 不应触达任何后端")
	}
}

func TestNoModelIDNoSessionBinding(t *testing.T) {
	deps, ifcFB, cadFB, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "get_script", `{}`)
	if !strings.Contains(out, "未绑定") && !strings.Contains(out, "modelId") {
		t.Fatalf("无 modelId 无绑定应提示: %s", out)
	}
	if ifcFB.count()+cadFB.count() != 0 {
		t.Fatal("守卫失败：无模型上下文不应触达任何后端")
	}
}

func TestSessionModelFallback(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	deps.SessionModel = func(ctx context.Context) string { return m.ID }
	out := invoke(t, DomainTools(deps), "get_script", `{}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("会话绑定模型回退失败: %s", out)
	}
	if last := ifcFB.last(); last.path != "/models/"+m.ID+"/script" {
		t.Fatalf("后端路径 = %s, want 会话绑定模型", last.path)
	}
}

func TestMarkDirtyNotCalledOnBackendFailure(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	var dirty bool
	deps.MarkDirty = func(ctx context.Context) { dirty = true }
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	ifcFB.status = http.StatusInternalServerError
	ifcFB.body = `{"detail":"sandbox boom"}`
	invoke(t, DomainTools(deps), "stage_script", `{"modelId":"`+m.ID+`","script":"x"}`)
	if dirty {
		t.Fatal("后端失败不应标记 dirty（变更未落地）")
	}
}

// --- agent 集成：工具错误的单卡映射 + ctx 会话注入 ---

func TestRunInjectsSessionIDToToolCtx(t *testing.T) {
	var gotSid string
	sidTool, err := newStringTool("whoami", func(ctx context.Context) (string, error) {
		gotSid = SessionIDFromContext(ctx)
		return "ok", nil
	})
	if err != nil {
		t.Fatal(err)
	}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(Script{Steps: []ScriptStep{
			{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "whoami", Arguments: `{}`}}},
			{Chunks: []string{"done"}},
		}})),
		WithTools([]tool.BaseTool{sidTool}),
	)
	if err != nil {
		t.Fatal(err)
	}
	events, err := ag.Run(context.Background(), "s_ctxinjection", "hi")
	if err != nil {
		t.Fatal(err)
	}
	collect(t, events)
	if gotSid != "s_ctxinjection" {
		t.Fatalf("工具 ctx 会话 id = %q, want s_ctxinjection", gotSid)
	}
}

// TestToolErrorEmitsErrorToolResult：工具返回 Go error（框架级失败）时，
// 事件流应给出带 error 载荷的 tool/result（前端渲染单卡错误态），
// 而非只有 session.error 横幅；lastErr 去重保证不重复上报。
func TestToolErrorEmitsErrorToolResult(t *testing.T) {
	boomTool, err := newStringTool("boom", func(ctx context.Context) (string, error) {
		return "", errors.New("kaboom")
	})
	if err != nil {
		t.Fatal(err)
	}
	ag, err := New(LLMConfig{},
		WithModel(NewScriptedModel(Script{Steps: []ScriptStep{
			{ToolCalls: []ToolCallSpec{{ID: "c1", Name: "boom", Arguments: `{}`}}},
		}})),
		WithTools([]tool.BaseTool{boomTool}),
	)
	if err != nil {
		t.Fatal(err)
	}
	events, err := ag.Run(context.Background(), "s_toolerror", "hi")
	if err != nil {
		t.Fatal(err)
	}
	evs := collect(t, events)
	var errResult, errEvent, turnEnd bool
	for _, ev := range evs {
		switch ev.Type {
		case EventToolResult:
			// eino 会包裹工具错误（[LocalFunc] failed to invoke tool … err=kaboom），
			// 断言含原始错误文本即可（LLM/前端可观测）。
			if e := payloadString(t, ev, "error"); strings.Contains(e, "kaboom") {
				errResult = true
			}
		case EventError:
			errEvent = true
		case EventTurnEnd:
			turnEnd = true
		}
	}
	if !errResult {
		t.Fatalf("缺带 error 载荷的 tool/result 事件: %v", eventTypes(evs))
	}
	if errEvent {
		t.Fatalf("工具错误不应再刷 session 级 error 事件（单卡映射替代）: %v", eventTypes(evs))
	}
	if !turnEnd {
		t.Fatalf("缺 turn/end 收尾: %v", eventTypes(evs))
	}
}
