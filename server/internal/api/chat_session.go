// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_session.go：会话 CRUD + 幂等处理（chatSessionId ↔ opencodeSessionId ↔ modelId）。
package api

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type chatSession struct {
	ID string `json:"chatSessionId"`
	// AgentID 是内置 agent 的会话 id（事件日志 {DataDir}/chat/{AgentID}.jsonl）。
	// JSON 字段名保留 opencodeSessionId——web client.ts 的 ChatSession 契约不动。
	AgentID string `json:"opencodeSessionId"`
	ModelID string `json:"modelId"`
	// ProjectID 是项目级绑定（A2：1 session = 1 project）。旧会话无 ProjectID
	// 视为单模型项目（模型即项目主体，兼容迁移）；幂等键 projectId 非空时优先。
	ProjectID string `json:"projectId,omitempty"`
	Title     string `json:"title"`
	CreatedAt string `json:"createdAt"`
	dirty     bool   `json:"-"` // write/edit 工具改过 uploads/{modelId}.ifc（file.edited 捕获）
	lastCheck time.Time `json:"-"` // 上次变更检测时刻；idle 时 mtime 晚于它即视为被改（兜底 bash/脚本改文件场景）
}

func (h *ChatHandler) sessionsPath() string {
	return filepath.Join(h.deps.DataDir, "chat-sessions.json")
}

// loadSessions 启动时恢复会话映射（文件不存在视为首次启动）。
// 去重：同 modelId 只保留最早 createdAt 一条——清理历史竞态残留（StrictMode 双发期产生），
// 保证 createSession 的幂等检查（map 遍历）稳定命中同一条，不会因 map 顺序随机导致历史时有时无。
func (h *ChatHandler) loadSessions() {
	data, err := os.ReadFile(h.sessionsPath())
	if err != nil {
		return
	}
	var list []*chatSession
	if err := json.Unmarshal(data, &list); err != nil {
		log.Printf("chat: load sessions: %v", err)
		return
	}
	earliest := map[string]*chatSession{} // modelId(非空) → 最早 createdAt
	var noModel []*chatSession            // 无 modelId 的不幂等，全部保留
	for _, cs := range list {
		if cs.ModelID == "" {
			noModel = append(noModel, cs)
			continue
		}
		if cur, ok := earliest[cs.ModelID]; !ok || cs.CreatedAt < cur.CreatedAt {
			earliest[cs.ModelID] = cs
		}
	}
	deduped := noModel
	for _, cs := range earliest {
		deduped = append(deduped, cs)
	}
	for _, cs := range deduped {
		cs.dirty = false
		cs.lastCheck = time.Now() // 防重启后 mtime 误判
		h.sessions[cs.ID] = cs
		h.byAgent[cs.AgentID] = cs.ID
	}
	if len(deduped) != len(list) {
		log.Printf("chat: dedup sessions %d → %d (清理同 modelId 竞态残留)", len(list), len(deduped))
		h.saveSessions() // 写回清理后的，避免下次再加载到重复
	} else if len(deduped) > 0 {
		log.Printf("chat: restored %d session(s)", len(deduped))
	}
}

// saveSessions 原子写会话映射（tmp + rename，同 viewer 原子写模式）。
func (h *ChatHandler) saveSessions() {
	h.mu.RLock()
	list := make([]*chatSession, 0, len(h.sessions))
	for _, cs := range h.sessions {
		list = append(list, cs)
	}
	h.mu.RUnlock()
	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		return
	}
	tmp := h.sessionsPath() + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		log.Printf("chat: save sessions: %v", err)
		return
	}
	if err := os.Rename(tmp, h.sessionsPath()); err != nil {
		log.Printf("chat: save sessions rename: %v", err)
	}
}

func newChatID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "c_" + hex.EncodeToString(b)
}

// newAgentSessionID 生成内置 agent 的会话 id（EventStore 文件名，须过 validateSessionID）。
func newAgentSessionID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return "s_" + hex.EncodeToString(b)
}

// findSession 按 modelId 查已绑定会话（空 modelId 永远不命中——不幂等）。
func (h *ChatHandler) findSession(modelID string) *chatSession {
	if modelID == "" {
		return nil
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, cs := range h.sessions {
		if cs.ModelID == modelID {
			return cs
		}
	}
	return nil
}

// findSessionByProject 按 projectId 查已绑定会话（A2：1 session = 1 project）。
func (h *ChatHandler) findSessionByProject(projectID string) *chatSession {
	if projectID == "" {
		return nil
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for _, cs := range h.sessions {
		if cs.ProjectID == projectID {
			return cs
		}
	}
	return nil
}

// createLock 返回某 modelId 专用的创建串行锁（同 modelId 并发请求共享同一把，互不阻塞其他 modelId）。
func (h *ChatHandler) createLock(key string) *sync.Mutex {
	h.createMu.Lock()
	defer h.createMu.Unlock()
	mu, ok := h.creating[key]
	if !ok {
		mu = &sync.Mutex{}
		h.creating[key] = mu
	}
	return mu
}

func (h *ChatHandler) createSession(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title     string `json:"title"`
		ModelID   string `json:"modelId"`
		ProjectID string `json:"projectId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	// A2：projectId 非空 → 项目必须存在（verify 层，业务规则不在 handler 内联）。
	// 项目绑定优先；无 projectId 时退回 modelId 幂等（旧语义：单模型项目）。
	if body.ProjectID != "" {
		if h.deps.Ps == nil {
			writeErr(w, http.StatusBadRequest, codeInvalidType, "project store 未配置")
			return
		}
		if _, err := h.deps.Ps.Get(body.ProjectID); err != nil {
			writeErr(w, http.StatusBadRequest, codeNotFound, "project not found: "+body.ProjectID)
			return
		}
		if existing := h.findSessionByProject(body.ProjectID); existing != nil {
			writeJSON(w, existing)
			return
		}
	}
	// 幂等：同一 modelId 只会有一个会话——退出再打开返回同一会话（会话连续性）。
	// 快速路径：读锁先查，命中即返回。
	if body.ModelID != "" {
		if existing := h.findSession(body.ModelID); existing != nil {
			writeJSON(w, existing)
			return
		}
	}
	if body.Title == "" {
		body.Title = "chat"
	}
	// per-modelId 串行创建：同 modelId 的并发请求在此互斥（StrictMode dev 双发 / 用户连点），
	// 网络往返在锁内但仅阻塞同 modelId；拿到锁后 double-check，已被别人建好就直接复用。
	cmu := h.createLock(body.ModelID + "|" + body.ProjectID)
	cmu.Lock()
	defer cmu.Unlock()
	if body.ProjectID != "" {
		if existing := h.findSessionByProject(body.ProjectID); existing != nil {
			writeJSON(w, existing)
			return
		}
	}
	if body.ModelID != "" {
		if existing := h.findSession(body.ModelID); existing != nil {
			writeJSON(w, existing)
			return
		}
	}
	cs := &chatSession{
		ID: newChatID(), AgentID: newAgentSessionID(), ModelID: body.ModelID,
		ProjectID: body.ProjectID, Title: body.Title, CreatedAt: time.Now().UTC().Format(time.RFC3339),
		lastCheck: time.Now(),
	}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byAgent[cs.AgentID] = cs.ID
	h.mu.Unlock()
	h.saveSessions()
	writeJSON(w, cs)
}

func (h *ChatHandler) listSessions(w http.ResponseWriter, r *http.Request) {
	h.mu.RLock()
	out := make([]*chatSession, 0, len(h.sessions))
	for _, cs := range h.sessions {
		out = append(out, cs)
	}
	h.mu.RUnlock()
	writeJSON(w, out)
}

func (h *ChatHandler) sessionOrErr(w http.ResponseWriter, cid string) *chatSession {
	h.mu.RLock()
	cs := h.sessions[cid]
	h.mu.RUnlock()
	if cs == nil {
		writeErr(w, http.StatusNotFound, codeNotFound, "chat session not found")
		return nil
	}
	return cs
}
