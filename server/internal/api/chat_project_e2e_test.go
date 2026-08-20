// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_project_e2e_test.go：新功能全链路连贯性测试（2026-08-20 九/十/十一波）。
//
// 场景：create_project（空白 + kind）→ 会话绑项目 → 方案级存储 PUT plan →
// agent 会话内 get_project_plans 读方案 → deliver_plan 交付（fake aiplan）→
// 方案版本化 + diff 可追溯。验证「项目容器 → 会话 → 方案 → 交付」连贯。
package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/store"
)

// newProjectE2EHandler 构造项目全链路 handler（Ps + PlanSt + AiplanBin fake）。
func newProjectE2EHandler(t *testing.T, script agent.Script) (*ChatHandler, *store.ProjectStore, *store.PlanStore) {
	t.Helper()
	dataDir := t.TempDir()
	st := store.NewStore(dataDir)
	ps := store.NewProjectStore(dataDir)
	planSt := store.NewPlanStore(dataDir)
	q := convert.NewQueue(st, okRunner{}, 1)
	// fake aiplan（writeFakeAiplan 在 chat_plan_test.go 同包）
	binDir := t.TempDir()
	fakeBin := binDir + "/aiplan"
	if err := writeFakeAiplan(t, fakeBin); err != nil {
		t.Fatal(err)
	}
	h := &ChatHandler{
		deps:     ChatDeps{St: st, Ps: ps, PlanSt: planSt, AiplanBin: fakeBin, Q: q, DataDir: dataDir},
		mux:      http.NewServeMux(),
		sessions: map[string]*chatSession{},
		byAgent:  map[string]string{},
		runs:     map[string]*chatRun{},
		subs:     map[string]map[chan []byte]struct{}{},
		creating: map[string]*sync.Mutex{},
	}
	h.registerRoutes()
	ag, err := agent.New(agent.LLMConfig{},
		agent.WithModel(agent.NewScriptedModel(script)),
		agent.WithStore(agent.NewEventStore(dataDir)),
		agent.WithTools(h.DomainTools()),
	)
	if err != nil {
		t.Fatalf("agent.New: %v", err)
	}
	h.SetAgent(ag)
	return h, ps, planSt
}

// TestProjectSessionFullChain 项目会话全链路：
// create_project(kind=cad) → 会话绑项目 → PUT plan → agent get_project_plans 读 →
// deliver_plan 交付 → 方案版本化 + diff 可追溯。
func TestProjectSessionFullChain(t *testing.T) {
	h, ps, planSt := newProjectE2EHandler(t, agent.Script{Steps: []agent.ScriptStep{
		{ToolCalls: []agent.ToolCallSpec{{ID: "p1", Name: "get_project_plans", Arguments: `{}`}}},
		{ToolCalls: []agent.ToolCallSpec{{ID: "d1", Name: "deliver_plan", Arguments: `{"plan":{"version":2,"project":"x"},"bimSupplement":{"version":1,"project":"x"}}`}}},
		{Chunks: []string{"方案已交付"}},
	}})

	// ① create_project（kind=cad 必选）→ 空白项目
	req := httptest.NewRequest(http.MethodPost, "/api/v1/chat/projects", strings.NewReader(`{"title":"全链路项目","kind":"cad"}`))
	rec := httptest.NewRecorder()
	h.mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("create_project status = %d body=%s", rec.Code, rec.Body.String())
	}
	var e struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &e)
	var p struct {
		ProjectID string `json:"projectId"`
		Kind      string `json:"kind"`
	}
	_ = json.Unmarshal(e.Data, &p)
	if p.ProjectID == "" || p.Kind != "cad" {
		t.Fatalf("create_project 返回 = %+v", p)
	}
	// 空白项目：无模型
	if ms, _ := h.deps.St.List(); len(ms) != 0 {
		t.Fatalf("空白项目不应产模型: %+v", ms)
	}

	// ② 会话绑项目（1 session = 1 project）
	cs := doChatCreateJSON(t, h, `{"title":"t","projectId":"`+p.ProjectID+`"}`)
	if cs.ProjectID != p.ProjectID {
		t.Fatalf("会话 projectId = %q, want %q", cs.ProjectID, p.ProjectID)
	}

	// ③ 方案级存储：PUT plan.json + bim_supplement.json（REST 层）
	put := httptest.NewRequest(http.MethodPut, "/api/v1/projects/"+p.ProjectID+"/plan.json",
		strings.NewReader(`{"content":{"version":1,"project":"`+p.ProjectID+`","site":{"area":100}}}`))
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, put)
	if rec.Code != http.StatusOK {
		t.Fatalf("PUT plan status = %d body=%s", rec.Code, rec.Body.String())
	}
	putBim := httptest.NewRequest(http.MethodPut, "/api/v1/projects/"+p.ProjectID+"/bim_supplement.json",
		strings.NewReader(`{"content":{"version":1,"project":"`+p.ProjectID+`"}}`))
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, putBim)
	if rec.Code != http.StatusOK {
		t.Fatalf("PUT bim status = %d body=%s", rec.Code, rec.Body.String())
	}

	// ④ 对话：agent 在项目会话内 get_project_plans → deliver_plan
	ch := h.subscribe(cs.ID)
	if code := postChat(t, h, cs.ID, "读方案并交付"); code != http.StatusOK {
		t.Fatalf("post status = %d", code)
	}
	frames := collectUntil(t, ch, "question.ask") // deliver_plan 被审批拦截（调了先问）
	var interruptID string
	for _, f := range frames {
		if frameEvent(f) == "question.ask" {
			interruptID = frameDataStr(t, f, "interruptId")
		}
	}
	if interruptID == "" {
		t.Fatalf("deliver_plan 应触发审批 question.ask")
	}
	// ⑤ /answer 确认 → 续跑 → session.idle
	resp := httptest.NewRequest(http.MethodPost, "/api/v1/chat/sessions/"+cs.ID+"/answer",
		strings.NewReader(`{"interruptId":"`+interruptID+`","answer":"确认"}`))
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, resp)
	if rec.Code != http.StatusOK {
		t.Fatalf("answer status = %d body=%s", rec.Code, rec.Body.String())
	}
	frames = append(frames, collectUntil(t, ch, "session.idle")...)

	// ⑥ 断言：plan 版本化（v1 → deliver 后 v2）——交付连贯
	cur, err := planSt.Get(p.ProjectID, "plan.json")
	if err != nil {
		t.Fatalf("deliver 后 plan 应落盘: %v", err)
	}
	if !strings.Contains(string(cur), `"version":2`) {
		t.Fatalf("deliver_plan 应产出 v2 plan: %s", cur)
	}
	hist, _ := planSt.ListHistory(p.ProjectID, "plan.json")
	if len(hist) != 1 || hist[0] != "v1" {
		t.Fatalf("history = %v, want [v1]（v1 归档）", hist)
	}
	// ⑦ 方案 diff 可追溯（v1 → current 字段级差异）
	diff := httptest.NewRequest(http.MethodGet, "/api/v1/projects/"+p.ProjectID+"/plan_history/v1/current/diff", nil)
	rec = httptest.NewRecorder()
	h.mux.ServeHTTP(rec, diff)
	if rec.Code != http.StatusOK {
		t.Fatalf("diff status = %d", rec.Code)
	}
	var de struct {
		Code int             `json:"code"`
		Data json.RawMessage `json:"data"`
	}
	_ = json.Unmarshal(rec.Body.Bytes(), &de)
	var dr struct {
		Changes []struct {
			Op   string `json:"op"`
			Path string `json:"path"`
		} `json:"changes"`
	}
	_ = json.Unmarshal(de.Data, &dr)
	if len(dr.Changes) == 0 {
		t.Fatalf("v1→current 应有 diff changes")
	}
	// ⑧ 会话内 agent 工具确实被调用（交付文本出现）
	if !strings.Contains(strings.Join(frames, "|"), "方案已交付") {
		t.Fatalf("agent 应产出汇总文本（交付连贯）")
	}
	_ = ps
}
