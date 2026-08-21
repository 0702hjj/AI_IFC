// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// kind_agent_test.go：WithKind 选择性装配契约（D13）。
//   - persona：cad→personaCAD、ifc→personaIFC、其余→显式/默认
//   - kindChildren：cad->ifc/空 全装 cad+ifc；cad 只 cad；ifc 只 ifc
//   - aiplan skill：cad/cad->ifc 挂 orchestrator；ifc 不挂（装配侧看 handlers 间接，persona 变化为准）
package agent

import (
	"strings"
	"testing"

	"github.com/cloudwego/eino/adk"
)

func TestWithKindPersona(t *testing.T) {
	cases := []struct {
		kind string
		want string // persona 关键片段
	}{
		{"cad", "CAD 项目"},
		{"ifc", "IFC 项目"},
		{"cad->ifc", "cad->ifc 项目"}, // cad->ifc 专属全链编排（kind 强制三选一，无空 kind）
	}
	for _, c := range cases {
		ag, err := New(LLMConfig{}, WithKind(c.kind))
		if err != nil {
			t.Fatalf("kind=%q: %v", c.kind, err)
		}
		if !strings.Contains(ag.Persona(), c.want) {
			t.Errorf("kind=%q persona 缺 %q，got %q…", c.kind, c.want, ag.Persona()[:60])
		}
	}
}

func TestWithKindPersonaOverridesDefault(t *testing.T) {
	// cad/ifc 的 kind 变体覆盖默认全装 persona（不依赖显式 WithPersona）
	ag, err := New(LLMConfig{}, WithKind("cad"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(ag.Persona(), "CAD 项目") {
		t.Errorf("kind=cad 应使用 personaCAD，got %q…", ag.Persona()[:60])
	}
	if strings.Contains(ag.Persona(), "ifc-agent") {
		t.Errorf("kind=cad persona 不应含 ifc 派发分支")
	}
}

func TestKindChildren(t *testing.T) {
	type fakeAgent struct{ adk.Agent }
	cad, ifc := fakeAgent{}, fakeAgent{}
	cases := []struct {
		kind string
		n    int
	}{
		{"cad->ifc", 2},
		{"cad", 1},
		{"ifc", 1},
		{"", 2}, // 空 = 全装（向后兼容）
	}
	for _, c := range cases {
		got := kindChildren(c.kind, cad, ifc)
		if len(got) != c.n {
			t.Errorf("kind=%q children=%d，期望 %d", c.kind, len(got), c.n)
		}
	}
	// 精确性：cad 只含 cad，ifc 只含 ifc
	if got := kindChildren("cad", cad, ifc); len(got) != 1 || got[0] != adk.Agent(cad) {
		t.Errorf("kind=cad 应只含 cad-agent")
	}
	if got := kindChildren("ifc", cad, ifc); len(got) != 1 || got[0] != adk.Agent(ifc) {
		t.Errorf("kind=ifc 应只含 ifc-agent")
	}
}

// TestCadAgentPersonaConsumesPlan cad-agent 必须显式消费 aiplan plan 产物：
// 执行前先 get_project_plans 读 plan.json + bim_supplement.json，plan 缺失报告不硬画。
func TestCadAgentPersonaConsumesPlan(t *testing.T) {
	if !strings.Contains(cadAgentPersona, "先消费 plan 再动手") {
		t.Error("cadAgentPersona 缺「先消费 plan 再动手」纪律")
	}
	if !strings.Contains(cadAgentPersona, "get_project_plans") {
		t.Error("cadAgentPersona 缺 get_project_plans 读 plan 工具指引")
	}
	if !strings.Contains(cadAgentPersona, "禁止无 plan 硬画") {
		t.Error("cadAgentPersona 缺 plan 缺失报告纪律")
	}
}

// TestOrchestratorPersonaContract 编排契约：三个 persona 的关键编排要素（步骤 + 产物锚点 + 断点）。
// kind 强制三选一（无空 kind）：OrchestratorPersona = cad->ifc 专属全链编排。
func TestOrchestratorPersonaContract(t *testing.T) {
	// OrchestratorPersona（cad->ifc 专属）：plan→cad→ifc 全链步骤 + 产物锚点 + 断点主持 + 消费上游路径
	if !strings.Contains(OrchestratorPersona, "cad->ifc 项目") ||
		!strings.Contains(OrchestratorPersona, "deliver_plan") ||
		!strings.Contains(OrchestratorPersona, "deliver_building") ||
		!strings.Contains(OrchestratorPersona, "stage_plan_to_workdir") ||
		!strings.Contains(OrchestratorPersona, "CONSUME_UPSTREAM") ||
		!strings.Contains(OrchestratorPersona, "断点主持") {
		t.Errorf("OrchestratorPersona 缺 cad->ifc 全链编排契约要素（步骤/产物锚点/断点/消费上游路径）")
	}
	// personaCAD：cad 管线步骤（aiplan 前置 + cad 出图 + building.json）
	if !strings.Contains(personaCAD, "aiplan") ||
		!strings.Contains(personaCAD, "deliver_building") ||
		!strings.Contains(personaCAD, "stage_plan_to_workdir") ||
		strings.Contains(personaCAD, "ifc-agent") {
		t.Errorf("personaCAD 应为 aiplan→cad 编排（不含 ifc 分支）")
	}
	// personaIFC：ifc 独立管线（design.json 前置 + 骨架深化）
	if !strings.Contains(personaIFC, "design.json 前置路径") ||
		!strings.Contains(personaIFC, "PLAN_DXF_IFC") ||
		!strings.Contains(personaIFC, "断点") {
		t.Errorf("personaIFC 应为 design.json 前置路径编排")
	}
}

// TestSubAgentPersonaPathDiscipline 子 agent 路径纪律：cad 消费 plan + ifc 路径由主 Agent 指定（不自己判断）。
func TestSubAgentPersonaPathDiscipline(t *testing.T) {
	if !strings.Contains(cadAgentPersona, "get_project_plans") ||
		!strings.Contains(cadAgentPersona, "plan.json") {
		t.Errorf("cadAgentPersona 应先消费 plan（get_project_plans 读 plan.json）")
	}
	if !strings.Contains(ifcAgentPersona, "路径由主 Agent 指定") ||
		!strings.Contains(ifcAgentPersona, "不自己判断") {
		t.Errorf("ifcAgentPersona 应为「路径由主 Agent 指定」（判断逻辑在 orchestrator）")
	}
}
