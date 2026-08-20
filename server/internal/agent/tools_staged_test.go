// tools_staged_test.go：run_script 中途预览契约——staging diff 摘要追加、
// PushStaged 信号、semanticDiff（构件级）优先与 null 回退、失败路径不推不拉。
package agent

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// --- run_script 中途预览：staging diff 摘要 + PushStaged 信号 ---

// stagedRunFixture 是路由感知的 run_script 测试后端：run 固定 200（body 可用
// runBody 覆盖，默认 {"ok":true}），staging diff 端点按 diffBody/diffStatus
// 应答（默认 404，模拟少于两个暂存步）。
type stagedRunFixture struct {
	mu         sync.Mutex
	diffCalls  int
	diffStatus int
	diffBody   string
	runBody    string
	srv        *httptest.Server
}

func newStagedRunFixture(t *testing.T, modelID string) *stagedRunFixture {
	t.Helper()
	f := &stagedRunFixture{
		diffStatus: http.StatusNotFound,
		diffBody:   `{"detail":"fewer than two staged steps"}`,
		runBody:    `{"ok":true}`,
	}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodPost && r.URL.Path == "/models/"+modelID+"/script/run":
			f.mu.Lock()
			body := f.runBody
			f.mu.Unlock()
			_, _ = io.WriteString(w, body)
		case r.Method == http.MethodGet && r.URL.Path == "/models/"+modelID+"/script/staging/diff":
			f.mu.Lock()
			f.diffCalls++
			status, body := f.diffStatus, f.diffBody
			f.mu.Unlock()
			w.WriteHeader(status)
			_, _ = io.WriteString(w, body)
		default:
			w.WriteHeader(http.StatusNotFound)
			_, _ = io.WriteString(w, `{"detail":"not scripted"}`)
		}
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func (f *stagedRunFixture) diffCallCount() int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.diffCalls
}

// TestRunScriptAppendsStagingDiffSummaryAndPushesStaged：run_script 成功后
// 工具结果追加 staging diff 摘要（added/removed 计数 + PARAMS 变化行），
// 并触发一次 PushStaged（modelId/kind）。
func TestRunScriptAppendsStagingDiffSummaryAndPushesStaged(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	fx := newStagedRunFixture(t, m.ID)
	fx.diffStatus = http.StatusOK
	fx.diffBody = `{"from":0,"to":1,"text_diff":"","stats":{"added":2,"removed":1},` +
		`"params_changes":[{"key":"width","action":"modified","old":3,"new":4},` +
		`{"key":"height","action":"added","new":2.8}]}`
	var pushes []string
	deps := ToolDeps{IFC: editsvc.New(fx.srv.URL), CAD: editsvc.New(fx.srv.URL), St: st}
	deps.PushStaged = func(ctx context.Context, modelID, kind string) {
		pushes = append(pushes, modelID+"|"+kind)
	}
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("run_script 输出 = %s", out)
	}
	if !strings.Contains(out, "added=2") || !strings.Contains(out, "removed=1") {
		t.Fatalf("工具结果缺 added/removed 计数摘要: %s", out)
	}
	if !strings.Contains(out, "width") || !strings.Contains(out, "height") {
		t.Fatalf("工具结果缺 PARAMS 变化行: %s", out)
	}
	if fx.diffCallCount() != 1 {
		t.Fatalf("staging diff 调用 = %d, want 1（轻量单次）", fx.diffCallCount())
	}
	if len(pushes) != 1 || pushes[0] != m.ID+"|ifc" {
		t.Fatalf("PushStaged = %v, want [%s|ifc]", pushes, m.ID)
	}
}

// TestRunScriptFailureSkipsSummaryAndStagedPush：run 失败 → 不推 staged、
// 不拉 diff、不追加摘要（错误文本化路径保持原样）。
func TestRunScriptFailureSkipsSummaryAndStagedPush(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	var mu sync.Mutex
	var diffCalls int
	failSrv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/script/staging/diff") {
			mu.Lock()
			diffCalls++
			mu.Unlock()
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, `{"detail":"sandbox boom"}`)
	}))
	t.Cleanup(failSrv.Close)
	var pushed bool
	deps := ToolDeps{IFC: editsvc.New(failSrv.URL), CAD: editsvc.New(failSrv.URL), St: st}
	deps.PushStaged = func(ctx context.Context, modelID, kind string) { pushed = true }
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, "调用失败") {
		t.Fatalf("run 失败应错误文本化: %s", out)
	}
	if pushed {
		t.Fatal("run 失败不应推 viewer.staged（变更未落地）")
	}
	mu.Lock()
	defer mu.Unlock()
	if diffCalls != 0 {
		t.Fatalf("run 失败不应拉 staging diff（调用 %d 次）", diffCalls)
	}
}

// TestRunScriptStagedPushSurvivesDiffUnavailable：staging diff 不可用
// （少于两个暂存步 409/404）时摘要降级为空，但 PushStaged 照推、结果不带摘要。
func TestRunScriptStagedPushSurvivesDiffUnavailable(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	fx := newStagedRunFixture(t, m.ID) // diff 默认 404
	var pushed bool
	deps := ToolDeps{IFC: editsvc.New(fx.srv.URL), CAD: editsvc.New(fx.srv.URL), St: st}
	deps.PushStaged = func(ctx context.Context, modelID, kind string) { pushed = true }
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("run_script 输出 = %s", out)
	}
	if strings.Contains(out, "added=") {
		t.Fatalf("diff 不可用时不应追加摘要: %s", out)
	}
	if !pushed {
		t.Fatal("diff 不可用不应阻塞 viewer.staged 推送（预览信号与摘要解耦）")
	}
}

// TestRunScriptPrefersSemanticDiffSummary：run 响应带构件级 semanticDiff 时
// 摘要优先用它（构件增减比行级 added/removed 对 AI 自纠更有用），
// 且不再回拉行级 staging diff。
func TestRunScriptPrefersSemanticDiffSummary(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	fx := newStagedRunFixture(t, m.ID)
	fx.runBody = `{"ok":true,"semanticDiff":{"added":2,"removed":1,"changed":3}}`
	// 行级 diff 也可用——必须不被消费（构件级优先）。
	fx.diffStatus = http.StatusOK
	fx.diffBody = `{"from":0,"to":1,"stats":{"added":9,"removed":9},"params_changes":[]}`
	deps := ToolDeps{IFC: editsvc.New(fx.srv.URL), CAD: editsvc.New(fx.srv.URL), St: st}
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, `"ok":true`) {
		t.Fatalf("run_script 输出 = %s", out)
	}
	if !strings.Contains(out, "构件 +2 -1 ~3") {
		t.Fatalf("工具结果缺构件级计数摘要: %s", out)
	}
	if strings.Contains(out, "added=9") {
		t.Fatalf("构件级可用时不应回退行级摘要: %s", out)
	}
	if fx.diffCallCount() != 0 {
		t.Fatalf("构件级可用时不应再拉 staging diff（调用 %d 次）", fx.diffCallCount())
	}
}

// TestRunScriptSemanticDiffNullFallsBackToLineSummary：run 响应 semanticDiff
// 为 null（diff 失败/无旧产物降级）时回退既有行级 staging diff 摘要。
func TestRunScriptSemanticDiffNullFallsBackToLineSummary(t *testing.T) {
	st := store.NewStore(t.TempDir())
	m := mustModel(t, st, "a.ifc", store.KindIFC)
	fx := newStagedRunFixture(t, m.ID)
	fx.runBody = `{"ok":true,"semanticDiff":null}`
	fx.diffStatus = http.StatusOK
	fx.diffBody = `{"from":0,"to":1,"stats":{"added":2,"removed":1},"params_changes":[]}`
	deps := ToolDeps{IFC: editsvc.New(fx.srv.URL), CAD: editsvc.New(fx.srv.URL), St: st}
	out := invoke(t, DomainTools(deps), "run_script", `{"modelId":"`+m.ID+`"}`)
	if !strings.Contains(out, "added=2") || !strings.Contains(out, "removed=1") {
		t.Fatalf("semanticDiff=null 应回退行级摘要: %s", out)
	}
	if fx.diffCallCount() != 1 {
		t.Fatalf("回退路径 staging diff 调用 = %d, want 1", fx.diffCallCount())
	}
}
