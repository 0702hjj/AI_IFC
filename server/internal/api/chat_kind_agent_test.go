// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_kind_agent_test.go：按项目类型（kind）路由主 agent 的契约测试。
// D13：AgentAsTool 选择性装配 + kind persona + aiplan 挂载差异——
// 会话（含历史项目会话恢复）经 agentForSession 按 Project.Kind 命中对应 agent。
package api

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
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

// TestDeleteProjectCascade 删除项目级联清理（单删除入口，绑定全套）：
// 项目 + 会话（chat-sessions）+ 事件日志 + 方案 + 项目下模型。
func TestDeleteProjectCascade(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, err := ps.CreateWithKind("待删项目", "cad")
	if err != nil {
		t.Fatal(err)
	}
	// 造会话 + 事件日志 + 方案 + 模型目录
	cs := &chatSession{ID: "s_del", AgentID: "a_del", ProjectID: p.ID}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byAgent[cs.AgentID] = cs.ID
	h.mu.Unlock()
	h.saveSessions()
	if err := os.MkdirAll(filepath.Join(h.deps.DataDir, "chat"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(h.deps.DataDir, "chat", cs.AgentID+".jsonl"), []byte("{}\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	// 方案产物
	if h.deps.PlanSt == nil {
		h.deps.PlanSt = store.NewPlanStore(h.deps.DataDir)
	}
	if _, err := h.deps.PlanSt.Put(p.ID, "plan.json", []byte(`{"project":"`+p.ID+`"}`)); err != nil {
		t.Fatal(err)
	}
	// skill 工作区（skill-work/{projectID}——aidxf 中间产物）
	workdir := filepath.Join(h.deps.DataDir, "skill-work", p.ID)
	if err := os.MkdirAll(filepath.Join(workdir, "missions"), 0o755); err != nil {
		t.Fatal(err)
	}

	req := httptest.NewRequest(http.MethodDelete, "/api/v1/chat/projects/"+p.ID, nil)
	req.SetPathValue("id", p.ID)
	rec := httptest.NewRecorder()
	h.deleteProject(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	// 项目已删
	if _, err := ps.Get(p.ID); err == nil {
		t.Error("项目未删")
	}
	// 会话已删
	h.mu.Lock()
	_, ok := h.sessions[cs.ID]
	h.mu.Unlock()
	if ok {
		t.Error("会话未删")
	}
	// 事件日志已删
	if _, err := os.Stat(filepath.Join(h.deps.DataDir, "chat", cs.AgentID+".jsonl")); err == nil {
		t.Error("事件日志未删")
	}
	// 方案已删
	if _, err := h.deps.PlanSt.Get(p.ID, "plan.json"); err == nil {
		t.Error("方案未删")
	}
	// skill 工作区已删（级联 2.5）
	if _, err := os.Stat(workdir); err == nil {
		t.Error("skill 工作区未删（级联清理缺失）")
	}
}

// TestDeleteProjectNotFound 删除不存在项目 → 404。
func TestDeleteProjectNotFound(t *testing.T) {
	h, _ := newKindAgentHandler(t)
	req := httptest.NewRequest(http.MethodDelete, "/api/v1/chat/projects/p_nonexist", nil)
	req.SetPathValue("id", "p_nonexist")
	rec := httptest.NewRecorder()
	h.deleteProject(rec, req)
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status=%d，期望 404", rec.Code)
	}
}


// TestSkillWorkDirForAgent skill 工作区：{DATA}/skill-work/{projectID} + MkdirAll + projectId 隔离。
func TestSkillWorkDirForAgent(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p1, _ := ps.CreateWithKind("项目1", "cad")
	p2, _ := ps.CreateWithKind("项目2", "cad")
	ctx := context.Background()

	d1, err := h.skillWorkDirForAgent(ctx, p1.ID)
	if err != nil {
		t.Fatalf("skillWorkDirForAgent: %v", err)
	}
	// 路径 = {DATA}/skill-work/{projectID}
	want1 := filepath.Join(h.deps.DataDir, "skill-work", p1.ID)
	if d1 != want1 {
		t.Errorf("工作区路径 = %q, want %q", d1, want1)
	}
	// 自动建目录
	if fi, err := os.Stat(d1); err != nil || !fi.IsDir() {
		t.Errorf("工作区目录未建: %v", err)
	}
	// projectId 隔离（两项目工作区不同）
	d2, err := h.skillWorkDirForAgent(ctx, p2.ID)
	if err != nil {
		t.Fatalf("skillWorkDirForAgent p2: %v", err)
	}
	if d1 == d2 {
		t.Errorf("两项目工作区应隔离（projectId 不同）: %q == %q", d1, d2)
	}
	// 幂等（再调不报错）
	if _, err := h.skillWorkDirForAgent(ctx, p1.ID); err != nil {
		t.Errorf("工作区幂等重建: %v", err)
	}
}

// TestPlanToWorkdirForAgent plan 桥接：PlanStore plan/bim → 工作区文件（内容一致 + 路径正确）。
func TestPlanToWorkdirForAgent(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, _ := ps.CreateWithKind("项目", "cad")
	if h.deps.PlanSt == nil {
		h.deps.PlanSt = store.NewPlanStore(h.deps.DataDir)
	}
	planContent := []byte(`{"project":"` + p.ID + `","zones":[]}`)
	bimContent := []byte(`{"roof":"flat"}`)
	if _, err := h.deps.PlanSt.Put(p.ID, "plan.json", planContent); err != nil {
		t.Fatal(err)
	}
	if _, err := h.deps.PlanSt.Put(p.ID, "bim_supplement.json", bimContent); err != nil {
		t.Fatal(err)
	}

	paths, err := h.planToWorkdirForAgent(context.Background(), p.ID)
	if err != nil {
		t.Fatalf("planToWorkdirForAgent: %v", err)
	}
	// 路径 = skill-work/{projectID}/plan.json + bim_supplement.json
	wantDir := filepath.Join(h.deps.DataDir, "skill-work", p.ID)
	if paths["planPath"] != filepath.Join(wantDir, "plan.json") {
		t.Errorf("planPath = %q, want %s", paths["planPath"], filepath.Join(wantDir, "plan.json"))
	}
	if paths["bimPath"] != filepath.Join(wantDir, "bim_supplement.json") {
		t.Errorf("bimPath = %q", paths["bimPath"])
	}
	// 文件落盘 + 内容一致
	gotPlan, err := os.ReadFile(paths["planPath"])
	if err != nil || string(gotPlan) != string(planContent) {
		t.Errorf("plan.json 落盘内容不一致: %v got %q", err, gotPlan)
	}
	gotBim, err := os.ReadFile(paths["bimPath"])
	if err != nil || string(gotBim) != string(bimContent) {
		t.Errorf("bim_supplement.json 落盘内容不一致: %v got %q", err, gotBim)
	}
}

// TestBuildingDeliverForAgent building.json 交付：PlanStore 版本化 plans/{projectID}/building.json。
func TestBuildingDeliverForAgent(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, _ := ps.CreateWithKind("项目", "cad")
	if h.deps.PlanSt == nil {
		h.deps.PlanSt = store.NewPlanStore(h.deps.DataDir)
	}
	building := `{"project":"` + p.ID + `","zones":[{"zone":"f1","modelId":"m_abc"}]}`
	v, err := h.buildingDeliverForAgent(context.Background(), p.ID, building)
	if err != nil {
		t.Fatalf("buildingDeliverForAgent: %v", err)
	}
	if v["buildingVersion"] == nil || v["buildingVersion"] == "" {
		t.Errorf("应返回 buildingVersion: %v", v)
	}
	// PlanStore 可读回（版本化 plans/{projectID}/building.json）
	got, err := h.deps.PlanSt.Get(p.ID, "building.json")
	if err != nil {
		t.Fatalf("building.json 未落 PlanStore: %v", err)
	}
	if !strings.Contains(string(got), "m_abc") {
		t.Errorf("building.json 内容不一致: %s", got)
	}
}

// TestUpstreamToWorkdirForAgent ifc 消费桥接：building+bim 落工作区 + 各 zone DXF 按 modelId 复制到 dxf/。
func TestUpstreamToWorkdirForAgent(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, _ := ps.CreateWithKind("项目", "cad->ifc")
	if h.deps.PlanSt == nil {
		h.deps.PlanSt = store.NewPlanStore(h.deps.DataDir)
	}
	// building.json（zones 记 modelId）+ bim_supplement.json
	mid := "m_0123456789abcdef"
	building := `{"version":2,"project":"` + p.ID + `","zones":[{"zone":"tower","floors_from":1,"floors_to":3,"modelId":"` + mid + `"}]}`
	if _, err := h.deps.PlanSt.Put(p.ID, "building.json", []byte(building)); err != nil {
		t.Fatal(err)
	}
	if _, err := h.deps.PlanSt.Put(p.ID, "bim_supplement.json", []byte(`{"roof":{"type":"gable"}}`)); err != nil {
		t.Fatal(err)
	}
	// 造 zone DXF（uploads/{modelId}.dxf 当前态）
	if err := os.MkdirAll(filepath.Join(h.deps.DataDir, "uploads"), 0o755); err != nil {
		t.Fatal(err)
	}
	dxfContent := []byte("0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
	if err := os.WriteFile(filepath.Join(h.deps.DataDir, "uploads", mid+".dxf"), dxfContent, 0o644); err != nil {
		t.Fatal(err)
	}

	out, err := h.upstreamToWorkdirForAgent(context.Background(), p.ID)
	if err != nil {
		t.Fatalf("upstreamToWorkdirForAgent: %v", err)
	}
	// building/bim 落工作区
	wantDir := filepath.Join(h.deps.DataDir, "skill-work", p.ID)
	if out["buildingPath"] != filepath.Join(wantDir, "building.json") {
		t.Errorf("buildingPath = %v", out["buildingPath"])
	}
	if out["bimPath"] != filepath.Join(wantDir, "bim_supplement.json") {
		t.Errorf("bimPath = %v", out["bimPath"])
	}
	// 各 zone DXF 复制到 dxf/<zone>.dxf
	dxfPaths, _ := out["dxfPaths"].(map[string]string)
	towerDxf := dxfPaths["tower"]
	if towerDxf != filepath.Join(wantDir, "dxf", "tower.dxf") {
		t.Errorf("tower DXF 路径 = %q", towerDxf)
	}
	got, err := os.ReadFile(towerDxf)
	if err != nil || string(got) != string(dxfContent) {
		t.Errorf("tower DXF 内容不一致: %v", err)
	}
}

// TestUpstreamToWorkdirMissingDxf zone DXF 缺失 → 报错（提示需先 init_model + run）。
func TestUpstreamToWorkdirMissingDxf(t *testing.T) {
	h, ps := newKindAgentHandler(t)
	p, _ := ps.CreateWithKind("项目", "cad->ifc")
	if h.deps.PlanSt == nil {
		h.deps.PlanSt = store.NewPlanStore(h.deps.DataDir)
	}
	building := `{"version":2,"project":"` + p.ID + `","zones":[{"zone":"tower","floors_from":1,"floors_to":1,"modelId":"m_9999999999999999"}]}`
	if _, err := h.deps.PlanSt.Put(p.ID, "building.json", []byte(building)); err != nil {
		t.Fatal(err)
	}
	if _, err := h.deps.PlanSt.Put(p.ID, "bim_supplement.json", []byte(`{}`)); err != nil {
		t.Fatal(err)
	}
	// uploads/m_999...dxf 不存在
	if _, err := h.upstreamToWorkdirForAgent(context.Background(), p.ID); err == nil {
		t.Error("zone DXF 缺失应报错（提示需先 init_model + run 产 DXF）")
	}
}
