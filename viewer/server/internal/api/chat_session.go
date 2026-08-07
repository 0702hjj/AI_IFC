// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// chat_session.go：会话 CRUD + 幂等处理（chatSessionId ↔ opencodeSessionId ↔ modelId）。
package api

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"
	"time"
)

type chatSession struct {
	ID         string    `json:"chatSessionId"`
	OpencodeID string    `json:"opencodeSessionId"`
	ModelID    string    `json:"modelId"`
	Title      string    `json:"title"`
	CreatedAt  string    `json:"createdAt"`
	dirty      bool      `json:"-"` // write/edit 工具改过 uploads/{modelId}.ifc（file.edited 捕获）
	lastCheck  time.Time `json:"-"` // 上次变更检测时刻；idle 时 mtime 晚于它即视为被改（兜底 bash/脚本改文件场景）
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
		h.byOC[cs.OpencodeID] = cs.ID
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
		Title   string `json:"title"`
		ModelID string `json:"modelId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "invalid json body")
		return
	}
	// 幂等：同一 modelId 只会有一个会话——退出再打开返回同一会话（会话连续性）。
	// 快速路径：读锁先查，命中即返回。
	if existing := h.findSession(body.ModelID); existing != nil {
		writeJSON(w, existing)
		return
	}
	if body.Title == "" {
		body.Title = "chat"
	}
	// per-modelId 串行创建：同 modelId 的并发请求在此互斥（StrictMode dev 双发 / 用户连点），
	// 网络往返在锁内但仅阻塞同 modelId；拿到锁后 double-check，已被别人建好就直接复用。
	cmu := h.createLock(body.ModelID)
	cmu.Lock()
	defer cmu.Unlock()
	if existing := h.findSession(body.ModelID); existing != nil {
		writeJSON(w, existing)
		return
	}
	s, err := h.deps.OC.CreateSession(r.Context(), body.Title)
	if err != nil {
		writeChatErr(w, err)
		return
	}
	cs := &chatSession{
		ID: newChatID(), OpencodeID: s.ID, ModelID: body.ModelID,
		Title: body.Title, CreatedAt: time.Now().UTC().Format(time.RFC3339),
		lastCheck: time.Now(),
	}
	h.mu.Lock()
	h.sessions[cs.ID] = cs
	h.byOC[cs.OpencodeID] = cs.ID
	h.mu.Unlock()
	h.saveSessions()
	writeJSON(w, cs)
}

// getMessages 透传 opencode 会话历史（重新打开时回填聊天内容）。
func (h *ChatHandler) getMessages(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	msgs, err := h.deps.OC.GetMessages(r.Context(), cs.OpencodeID)
	if err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, msgs)
}

// abortSession 中止 AI 当前 turn（透传 opencode POST /session/{ocId}/abort）。
// 前端在 busy 时把"发送"钮变"停止"调此端点；opencode 随后发 session.idle + 进行中 part 的 removed。
func (h *ChatHandler) abortSession(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	if err := h.deps.OC.Abort(r.Context(), cs.OpencodeID); err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, map[string]bool{"aborted": true})
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

func (h *ChatHandler) postMessage(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	var body struct {
		Text string `json:"text"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || body.Text == "" {
		writeErr(w, http.StatusBadRequest, codeInvalidType, "text required")
		return
	}
	text := body.Text
	if cs.ModelID != "" {
		sys := fmt.Sprintf("当前会话绑定模型文件 viewer/data/uploads/%s.ifc（改它即改该模型；若是从零构建需求，该文件初始为骨架，直接在其上建造）。本会话 chatSessionId：%s。",
			cs.ModelID, cs.ID)
		// W-0016：≥2 个脚本大版本时追加「与上一大版本的脚本 diff」上下文（拉取失败自动降级）。
		if dc := h.scriptDiffContext(r.Context(), cs.ModelID); dc != "" {
			sys += "\n" + dc
		}
		text = "[系统上下文] " + sys + "\n\n[用户需求] " + body.Text
	}
	if err := h.deps.OC.PromptAsync(r.Context(), cs.OpencodeID, text, h.agent); err != nil {
		writeChatErr(w, err)
		return
	}
	writeJSON(w, map[string]bool{"accepted": true})
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
