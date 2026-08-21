// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_kind_agent_test.go：按项目类型（kind）路由主 agent 的契约测试。
// D13：AgentAsTool 选择性装配 + kind persona + aiplan 挂载差异——
// 会话（含历史项目会话恢复）经 agentForSession 按 Project.Kind 命中对应 agent。
package api

import (
	"net/http"
	"strings"
	"sync"
	"testing"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

// newKindAgentHandler 构造带 Agents 分化集 + ProjectStore 的 chat handler。
// 三种 kind agent 用不同 persona 标记（测试用 WithPersona 注入指纹，运行时
// 与生产装配差异：生产 kind agent 不显式传 persona，内部按 kind 选变体）。
func newKindAgentHandler(t *testing.T) (*ChatHandler, *store.ProjectStore) {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	q := convert.NewQueue(st, okRunner{}, 1)
	h := &ChatHandler{
		deps:     ChatDeps{St: st, Ps: ps, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()

	newAgent := func(kind string) *agent.Agent {
		ag, err := agent.New(agent.LLMConfig{},
			agent.WithModel(agent.NewScriptedModel(agent.Script{})),
			agent.WithStore(agent.NewEventStore(dataDir)),
			agent.WithTools(h.DomainTools()),
			agent.WithPersona("PERSONA["+kind+"]"),
		)
		if err != nil {
			t.Fatalf("agent.New(%s): %v", kind, err)
		}
		return ag
	}
	h.SetAgent(newAgent("default"))
	h.SetAgents(map[string]*agent.Agent{
		"cad":      newAgent("cad"),
		"ifc":      newAgent("ifc"),
		"cad->ifc": newAgent("cad->ifc"),
	})
	return h, ps
}

// TestAgentForSessionByKind 按项目类型路由主 agent：会话绑定 projectId →
// Project.Kind → 命中 Agents[kind]；历史项目会话（重启恢复）同样命中。
func TestAgentForSessionByKind(t *testing.T) {
	h, ps := newKindAgentHandler(t)

	// 三种 kind 项目 + 会话
	kinds := []string{"cad", "ifc", "cad->ifc"}
	for _, k := range kinds {
		p, err := ps.CreateWithKind("项目-"+k, k)
		if err != nil {
			t.Fatal(err)
		}
		cs := &chatSession{ID: "s_" + k, AgentID: "a_" + k, ProjectID: p.ID}
		got := h.agentForSession(cs)
		if got == nil {
			t.Fatalf("kind=%s: agentForSession 返回 nil", k)
		}
		// persona 指纹：生产 agent 的 kind 变体在 agent 层（本测试用 persona 指纹验证路由）
		if !strings.Contains(got.Persona(), "PERSONA["+k+"]") {
			t.Errorf("kind=%s: 路由到 persona %q，期望 PERSONA[%s]", k, got.Persona(), k)
		}
	}
}

// TestAgentForSessionHistoricSession 历史项目会话恢复（重启后从 sessions 文件
// 加载，只有 chatSession 无新会话创建）——同样按 ProjectID 命中 kind agent。
func TestAgentForSessionHistoricSession(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, err := ps.CreateWithKind("历史项目", "ifc")
	if err != nil {
		t.Fatal(err)
	}
	// 模拟重启恢复：直接构造带 ProjectID 的会话（不经过 createSession）
	cs := &chatSession{ID: "s_hist", AgentID: "a_hist", ProjectID: p.ID}
	got := h.agentForSession(cs)
	if got == nil || !strings.Contains(got.Persona(), "PERSONA[ifc]") {
		t.Fatalf("历史项目会话未命中 ifc agent，got persona=%v", got)
	}
}

// TestAgentForSessionFallback 无项目绑定/未知 kind → 落默认 agent（全装）。
func TestAgentForSessionFallback(t *testing.T) {
	h, _ := newKindAgentHandler(t)
	// 模型会话（无 ProjectID）→ 默认
	cs := &chatSession{ID: "s_model", AgentID: "a_model", ModelID: "m_x"}
	if got := h.agentForSession(cs); got == nil || !strings.Contains(got.Persona(), "PERSONA[default]") {
		t.Errorf("模型会话应落默认 agent")
	}
	// 项目存在但 kind 空 → 默认
	p, _ := h.deps.Ps.CreateWithKind("无类型", "")
	cs2 := &chatSession{ID: "s_none", AgentID: "a_none", ProjectID: p.ID}
	if got := h.agentForSession(cs2); got == nil || !strings.Contains(got.Persona(), "PERSONA[default]") {
		t.Errorf("kind 空项目应落默认 agent")
	}
	// Agents map 缺该 kind → 默认
	p3, _ := h.deps.Ps.CreateWithKind("异类", "weird")
	cs3 := &chatSession{ID: "s_w", AgentID: "a_w", ProjectID: p3.ID}
	if got := h.agentForSession(cs3); got == nil || !strings.Contains(got.Persona(), "PERSONA[default]") {
		t.Errorf("未知 kind 应落默认 agent")
	}
}
