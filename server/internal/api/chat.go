// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat 模块（demo）：对话式 AI 建模。独立 Handler，与既有 NewHandler 并列挂载
// （main.go 组合 root mux），不触碰既有路由。按职责分文件：
//
//	chat.go               路由注册 + handler 装配 + 共享类型
//	chat_session.go       会话 CRUD + 幂等（creating map）+ 映射表持久化
//	chat_eino.go          消息下发（Eino agent 运行）+ 历史回填 + 中止
//	chat_translate.go     agent Event → opencode 形状 SSE 帧翻译 + 历史投影
//	chat_sse.go           SSE 事件流 + pushLocked + 订阅管理
//	chat_orchestrator.go  turn 结束触发 notify + 制品归档 + 骨架 IFC 模板/GlobalId 生成
package api

import (
	"net/http"
	"sync"

	"ifcviewer/server/internal/agent"
	"ifcviewer/server/internal/convert"
	"ifcviewer/server/internal/editsvc"
	"ifcviewer/server/internal/store"
)

// ChatDeps 是 chat 模块的依赖包（agent 运行 + 事件日志 + notify 落盘 + 重转 + 脚本管线）。
type ChatDeps struct {
	Ag      *agent.Agent
	Ev      *agent.EventStore
	Ed      *editsvc.Client // ifc kind 后端（services/ifc :8100）
	Cad     *editsvc.Client // dxf kind 后端（services/cad :8200）；nil 时 dxf 会话 notify 报错文本
	St      *store.Store
	Ps      *store.ProjectStore // 项目级聚合（A1：create_project 项目级）；nil 时 create_project 降级单模型
	PlanSt  *store.PlanStore    // 方案级存储（B1：plans/{projectID}/plan.json + bim_supplement.json + 版本化）
	Q       *convert.Queue
	DataDir string
}

// editClientForKind 按模型 kind 选编辑后端（dxf→Cad，ifc/未知→Ed）。
// 未知模型/未配置后端返回 nil——调用方错误文本化（工具面）或降级（notify 面）。
func (d ChatDeps) editClientForKind(m *store.Model) *editsvc.Client {
	if m != nil && m.Kind == store.KindDXF {
		return d.Cad
	}
	return d.Ed
}

// ChatHandler 是 chat 模块的 HTTP handler（内部小 mux + 会话 map + 事件分发 + notify 触发）。
type ChatHandler struct {
	deps ChatDeps
	mux  *http.ServeMux

	mu       sync.RWMutex
	sessions map[string]*chatSession             // chatSessionId → session
	byAgent  map[string]string                   // agentSessionId → chatSessionId
	runs     map[string]*chatRun                 // chatSessionId → 进行中 turn 的登记项（abort + 条件删除）
	subs     map[string]map[chan []byte]struct{} // chatSessionId → 浏览器 SSE 订阅者集合
	seq      map[string]uint64                   // chatSessionId → 已分配的最大 SSE 事件 id
	evLog    map[string][]sseEvent               // chatSessionId → 重同步环形缓冲（id 升序，≤ sseReplayBufferSize）

	createMu sync.Mutex             // 仅保护下面的 creating map
	creating map[string]*sync.Mutex // per-modelId 创建串行锁：根治同 modelId 并发 createSession 的 TOCTOU 竞态
}

// NewChatHandler 创建 chat 模块 handler。
// 会话映射持久化在 {DataDir}/chat-sessions.json（原子写）；会话事件史在
// {DataDir}/chat/{agentSessionId}.jsonl（EventStore），server 重启后会话连续性仍在。
func NewChatHandler(d ChatDeps) *ChatHandler {
	h := &ChatHandler{
		deps: d, mux: http.NewServeMux(),
		sessions: map[string]*chatSession{}, byAgent: map[string]string{},
		runs: map[string]*chatRun{},
		subs: map[string]map[chan []byte]struct{}{}, creating: map[string]*sync.Mutex{},
		seq: map[string]uint64{}, evLog: map[string][]sseEvent{},
	}
	h.loadSessions()
	h.registerRoutes()
	return h
}

// registerRoutes 注册 chat 模块全部路由（NewChatHandler 与测试 handler 共用）。
func (h *ChatHandler) registerRoutes() {
	h.mux.HandleFunc("POST /api/v1/chat/sessions", h.createSession)
	h.mux.HandleFunc("GET /api/v1/chat/sessions", h.listSessions)
	h.mux.HandleFunc("POST /api/v1/chat/sessions/{cid}/messages", h.postMessage)
	h.mux.HandleFunc("GET /api/v1/chat/sessions/{cid}/messages", h.getMessages)
	h.mux.HandleFunc("GET /api/v1/chat/sessions/{cid}/events", h.events)
	h.mux.HandleFunc("POST /api/v1/chat/sessions/{cid}/abort", h.abortSession)
	h.mux.HandleFunc("POST /api/v1/chat/projects", h.createProject)
	// B1 方案级存储（交付对齐）：项目资源下的 plan 产物（plan/cad/ifc 共享项目，
	// plan.json/bim_supplement.json 挂项目资源前缀，非 chat 专属模块）
	h.mux.HandleFunc("GET /api/v1/projects/{projectID}/{name}", h.getPlanFile)
	h.mux.HandleFunc("PUT /api/v1/projects/{projectID}/{name}", h.putPlanFile)
	h.mux.HandleFunc("GET /api/v1/projects/{projectID}/plan_history", h.listPlanHistory)
}

func (h *ChatHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) { h.mux.ServeHTTP(w, r) }

// writeChatErr 把 chat 运行错误映射为 envelope（agent 未装配/运行失败 → 502）。
// opencode 客户端已退役（Eino 进程内接管），上游错误只剩 agent/edit-service 一类。
func writeChatErr(w http.ResponseWriter, err error) {
	writeErr(w, http.StatusBadGateway, codeBadGateway, err.Error())
}
