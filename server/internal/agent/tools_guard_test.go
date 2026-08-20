// tools_guard_test.go：错误文本化/截断、kind 路由（双 fake 钉死）与
// 模型上下文守卫（未知/非法/缺失 modelId 不触达后端）测试。
package agent

import (
	"context"
	"net/http"
	"strings"
	"testing"

	"ifcviewer/server/internal/store"
)

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
	if !ifcFB.saw(http.MethodPost, "/models/"+m.ID+"/script/run") {
		t.Fatalf("ifc 后端未收到 POST /models/%s/script/run", m.ID)
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
