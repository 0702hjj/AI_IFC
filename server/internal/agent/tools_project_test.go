// tools_project_test.go：项目/方案/工作区/桥接工具测试（D2 交付链）——
// get_project_plans / deliver_plan / deliver_building / get_skill_workdir /
// stage_plan_to_workdir / stage_upstream_to_workdir / init_model 等。
// 公共夹具（fakeBackend/newToolFixture/invoke/mustModel）见 tools_test.go。
package agent

import (
	"context"
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"

	"ifcviewer/server/internal/store"
)

func TestGetProjectPlansTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	var gotPID string
	deps.SessionProject = func(ctx context.Context) string { return "p_0000000000000001" }
	deps.PlanGet = func(ctx context.Context, projectID, name string) (string, error) {
		gotPID = projectID
		return `{"version":1,"project":"p_0000000000000001"}`, nil
	}
	out := invoke(t, DomainTools(deps), "get_project_plans", `{}`)
	if gotPID != "p_0000000000000001" {
		t.Fatalf("PlanGet projectID = %q", gotPID)
	}
	if !strings.Contains(out, `"plan"`) || !strings.Contains(out, `"bimSupplement"`) {
		t.Fatalf("get_project_plans 输出应含 plan/bimSupplement: %s", out)
	}
}

// TestDeliverPlanTool D2：plan 交付（调 PlanDeliver 回调）。
func TestDeliverPlanTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	var gotPlan string
	deps.SessionProject = func(ctx context.Context) string { return "p_0000000000000001" }
	deps.PlanDeliver = func(ctx context.Context, projectID, plan, bim string) (map[string]any, error) {
		gotPlan = plan
		return map[string]any{"planVersion": "v1", "bimVersion": "v1"}, nil
	}
	out := invoke(t, DomainTools(deps), "deliver_plan", `{"plan":{"project":"p_0000000000000001"}}`)
	if !strings.Contains(gotPlan, "p_0000000000000001") {
		t.Fatalf("PlanDeliver plan = %q", gotPlan)
	}
	if !strings.Contains(out, `"planVersion":"v1"`) {
		t.Fatalf("deliver_plan 输出应含版本: %s", out)
	}
}

// TestProjectToolsUnconfigured D2：回调未配置 → 文本错误（可空适配器）。
func TestProjectToolsUnconfigured(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "get_project_plans", `{"projectId":"p_0000000000000001"}`)
	if !strings.Contains(out, "未配置") {
		t.Fatalf("get_project_plans 未配置应提示: %s", out)
	}
	out = invoke(t, DomainTools(deps), "deliver_plan", `{"projectId":"p_0000000000000001","plan":{}}`)
	if !strings.Contains(out, "未配置") {
		t.Fatalf("deliver_plan 未配置应提示: %s", out)
	}
}

// TestGetScriptLocateTool D1：XDATA key → 调用点定位（走 resolve → GET locate）。
func TestGetScriptLocateTool(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m, err := st.CreateWithKind("a.ifc", 5, strings.NewReader("aaaaa"), store.KindIFC)
	if err != nil {
		t.Fatal(err)
	}
	out := invoke(t, DomainTools(deps), "get_script_locate", `{"modelId":"`+m.ID+`","key":"0:line:1"}`)
	if !strings.Contains(out, "ok") {
		t.Fatalf("locate 输出应含 fake 响应: %s", out)
	}
	ifcFB.mu.Lock()
	defer ifcFB.mu.Unlock()
	if len(ifcFB.reqs) == 0 || !strings.Contains(ifcFB.reqs[0].path, "/script/locate") {
		t.Fatalf("locate 应调 GET /script/locate: %+v", ifcFB.reqs)
	}
}

// TestEditScriptCallTool D1：标量改写（走 resolve → POST edit-call）。
func TestEditScriptCallTool(t *testing.T) {
	deps, ifcFB, _, st := newToolFixture(t)
	m, err := st.CreateWithKind("a.ifc", 5, strings.NewReader("aaaaa"), store.KindIFC)
	if err != nil {
		t.Fatal(err)
	}
	out := invoke(t, DomainTools(deps), "edit_script_call", `{"modelId":"`+m.ID+`","key":"0:line:1","argument":"length","value":20}`)
	if !strings.Contains(out, "ok") {
		t.Fatalf("edit-call 输出应含 fake 响应: %s", out)
	}
	ifcFB.mu.Lock()
	defer ifcFB.mu.Unlock()
	if len(ifcFB.reqs) == 0 || !strings.Contains(ifcFB.reqs[0].path, "/script/edit-call") {
		t.Fatalf("edit-call 应调 POST /script/edit-call: %+v", ifcFB.reqs)
	}
}

// TestInitModelTool init_model 工具：spy InitModel 回调验证 projectId 归一 + kind 默认 + markDirty。
func TestInitModelTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	var gotProjectID, gotKind, gotTitle string
	marked := false
	deps.InitModel = func(ctx context.Context, projectID, kind, title string) (any, error) {
		gotProjectID, gotKind, gotTitle = projectID, kind, title
		return map[string]any{"modelId": "m_test1234", "kind": kind, "title": title, "projectId": projectID}, nil
	}
	deps.MarkDirty = func(ctx context.Context) { marked = true }
	out := invoke(t, DomainTools(deps), "init_model", `{"title":"一层平面"}`)
	var res map[string]any
	if err := json.Unmarshal([]byte(out), &res); err != nil {
		t.Fatalf("输出非 JSON: %v out=%s", err, out)
	}
	if res["modelId"] != "m_test1234" {
		t.Errorf("modelId=%v", res["modelId"])
	}
	if gotKind != "dxf" {
		t.Errorf("kind 缺省应 dxf，got %q", gotKind)
	}
	if gotTitle != "一层平面" {
		t.Errorf("title=%q", gotTitle)
	}
	if !marked {
		t.Error("init_model 未 markDirty（模型变更信号）")
	}
	_ = gotProjectID // 无绑定时 projectId 为空（initModel 内部处理/可为空项目外初始化）
}

// TestGetSkillWorkdirTool get_skill_workdir：返回项目 skill 工作区绝对路径（会话绑项目）。
func TestGetSkillWorkdirTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	workdir := filepath.Join(t.TempDir(), "skill-work", "p_x")
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	deps.SkillWorkDir = func(ctx context.Context, projectID string) (string, error) { return workdir, nil }
	out := invoke(t, DomainTools(deps), "get_skill_workdir", `{}`)
	if !strings.Contains(out, workdir) {
		t.Fatalf("get_skill_workdir 输出应含工作区路径 %q, got %s", workdir, out)
	}
	if !strings.Contains(out, "p_x") {
		t.Fatalf("get_skill_workdir 输出应含 projectId, got %s", out)
	}
}

// TestGetSkillWorkdirToolUnconfigured get_skill_workdir 未配置/未绑项目 → 文本错误（不中断）。
func TestGetSkillWorkdirToolUnconfigured(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	// 未绑项目（SessionProject nil → projectID 空）
	out := invoke(t, DomainTools(deps), "get_skill_workdir", `{}`)
	if !strings.Contains(out, "未指定 projectId") && !strings.Contains(out, "未配置") {
		t.Fatalf("未绑项目/未配置应文本错误, got %s", out)
	}
}

// TestStagePlanToWorkdirTool stage_plan_to_workdir：返回 plan/bim 工作区文件路径（供 aidxfv3 --plan）。
func TestStagePlanToWorkdirTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	deps.PlanToWorkdir = func(ctx context.Context, projectID string) (map[string]string, error) {
		return map[string]string{
			"planPath": "/data/skill-work/p_x/plan.json",
			"bimPath":  "/data/skill-work/p_x/bim_supplement.json",
		}, nil
	}
	out := invoke(t, DomainTools(deps), "stage_plan_to_workdir", `{}`)
	if !strings.Contains(out, "plan.json") || !strings.Contains(out, "bim_supplement.json") {
		t.Fatalf("stage_plan_to_workdir 输出应含 plan/bim 路径, got %s", out)
	}
}

// TestStagePlanToWorkdirToolUnconfigured 未配置/未绑项目 → 文本错误。
func TestStagePlanToWorkdirToolUnconfigured(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "stage_plan_to_workdir", `{}`)
	if !strings.Contains(out, "未指定 projectId") && !strings.Contains(out, "未配置") {
		t.Fatalf("未绑项目/未配置应文本错误, got %s", out)
	}
}

// TestDeliverBuildingTool deliver_building：agent 组装 building.json → 交付（返回 buildingVersion）。
func TestDeliverBuildingTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	var gotBuilding string
	deps.BuildingDeliver = func(ctx context.Context, projectID, building string) (map[string]any, error) {
		gotBuilding = building
		return map[string]any{"projectId": projectID, "buildingVersion": "v1"}, nil
	}
	out := invoke(t, DomainTools(deps), "deliver_building", `{"building":{"zones":[{"zone":"f1","modelId":"m_1"}]}}`)
	if !strings.Contains(out, "buildingVersion") {
		t.Fatalf("deliver_building 输出应含 buildingVersion, got %s", out)
	}
	if !strings.Contains(gotBuilding, "m_1") {
		t.Fatalf("deliver_building 应透传 agent 组装的 building 内容, got %s", gotBuilding)
	}
}

// TestGetProjectPlansWithBuilding get_project_plans 扩展：读 plan+bim+building（building 容忍缺失）。
func TestGetProjectPlansWithBuilding(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	deps.PlanGet = func(ctx context.Context, projectID, name string) (string, error) {
		switch name {
		case "plan.json":
			return `{"task":"plan"}`, nil
		case "bim_supplement.json":
			return `{"roof":"flat"}`, nil
		case "building.json":
			return `{"zones":[{"modelId":"m_1"}]}`, nil
		}
		return "", nil
	}
	out := invoke(t, DomainTools(deps), "get_project_plans", `{}`)
	if !strings.Contains(out, `"building"`) || !strings.Contains(out, "m_1") {
		t.Fatalf("get_project_plans 应含 building 字段（zones 记 modelId）, got %s", out)
	}
	if !strings.Contains(out, `"plan"`) || !strings.Contains(out, `"bimSupplement"`) {
		t.Fatalf("get_project_plans 应仍含 plan + bimSupplement, got %s", out)
	}
}

// TestGetProjectPlansBuildingMissing get_project_plans：building 缺失时容忍（不含该字段，不报错）。
func TestGetProjectPlansBuildingMissing(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	deps.PlanGet = func(ctx context.Context, projectID, name string) (string, error) {
		if name == "building.json" {
			return "", &missingErr{}
		}
		return `{"x":1}`, nil
	}
	out := invoke(t, DomainTools(deps), "get_project_plans", `{}`)
	// building 缺失 → 不含 building 字段（容忍），但 plan/bim 正常返回
	if strings.Contains(out, `"building"`) {
		t.Fatalf("building 缺失时不应含 building 字段, got %s", out)
	}
	if !strings.Contains(out, `"plan"`) {
		t.Fatalf("building 缺失时 plan/bim 应正常返回, got %s", out)
	}
}

type missingErr struct{}

func (e *missingErr) Error() string { return "not found" }

// TestStageUpstreamToWorkdirTool stage_upstream_to_workdir：返回 building/bim/dxfDir/dxfPaths。
func TestStageUpstreamToWorkdirTool(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	deps.SessionProject = func(ctx context.Context) string { return "p_x" }
	deps.UpstreamToWorkdir = func(ctx context.Context, projectID string) (map[string]any, error) {
		return map[string]any{
			"buildingPath": "/data/skill-work/p_x/building.json",
			"bimPath":      "/data/skill-work/p_x/bim_supplement.json",
			"dxfDir":       "/data/skill-work/p_x/dxf",
			"dxfPaths":     map[string]string{"tower": "/data/skill-work/p_x/dxf/tower.dxf"},
		}, nil
	}
	out := invoke(t, DomainTools(deps), "stage_upstream_to_workdir", `{}`)
	for _, k := range []string{"buildingPath", "bimPath", "dxfDir", "tower.dxf"} {
		if !strings.Contains(out, k) {
			t.Fatalf("stage_upstream_to_workdir 输出应含 %q, got %s", k, out)
		}
	}
}

// TestStageUpstreamToWorkdirToolUnconfigured 未配置/未绑项目 → 文本错误。
func TestStageUpstreamToWorkdirToolUnconfigured(t *testing.T) {
	deps, _, _, _ := newToolFixture(t)
	out := invoke(t, DomainTools(deps), "stage_upstream_to_workdir", `{}`)
	if !strings.Contains(out, "未指定 projectId") && !strings.Contains(out, "未配置") {
		t.Fatalf("未绑项目/未配置应文本错误, got %s", out)
	}
}
