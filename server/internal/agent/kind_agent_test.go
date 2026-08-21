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
		{"cad->ifc", "帮助设计师通过对话完成"}, // 全装：不替换默认 persona
		{"", "帮助设计师通过对话完成"},           // 空 = 全装默认
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
