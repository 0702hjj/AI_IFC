// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_eino.go：消息下发（内置 Eino agent 运行）+ 事件流消费 + 历史回填 + 中止。
// 浏览器可见的 SSE/REST 契约与 opencode 时代完全一致（翻译层见 chat_translate.go）。
package api

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"

	"ifcviewer/server/internal/agent"
)

// errAgentNotConfigured 是 handler 装配缺 agent 时的哨兵错误（502 翻译）。
var errAgentNotConfigured = errors.New("chat agent not configured")

// postMessage 下发用户消息：拼系统上下文（格式与旧版逐字一致）后启动一轮
// agent ReAct 循环，事件流经翻译层推给 SSE 订阅者；循环结束触发 notify 判定。
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
	if h.deps.Ag == nil {
		writeChatErr(w, errAgentNotConfigured)
		return
	}
	text := body.Text
	if cs.ModelID != "" {
		sys := fmt.Sprintf("当前会话绑定模型文件 data/uploads/%s.ifc（改它即改该模型；若是从零构建需求，该文件初始为骨架，直接在其上建造）。本会话 chatSessionId：%s。",
			cs.ModelID, cs.ID)
		// W-0016：≥2 个脚本大版本时追加「与上一大版本的脚本 diff」上下文（拉取失败自动降级）。
		if dc := h.scriptDiffContext(r.Context(), cs.ModelID); dc != "" {
			sys += "\n" + dc
		}
		text = "[系统上下文] " + sys + "\n\n[用户需求] " + body.Text
	}
	ctx, cancel := context.WithCancel(context.Background())
	events, err := h.deps.Ag.Run(ctx, cs.AgentID, text)
	if err != nil {
		cancel()
		writeChatErr(w, err)
		return
	}
	h.mu.Lock()
	if h.runs == nil { // 兼容测试手工构造的 handler
		h.runs = map[string]context.CancelFunc{}
	}
	prev := h.runs[cs.ID]
	h.runs[cs.ID] = cancel
	h.mu.Unlock()
	if prev != nil { // 同会话串发：取消上一跑（防御，正常前端 busy 期不会再发）
		prev()
	}
	go h.consumeRun(cs, events)
	writeJSON(w, map[string]bool{"accepted": true})
}

// consumeRun 消费一轮 agent 事件流：翻译为 opencode 形状 SSE 帧推送；
// 流关闭（turn/end 已发）后做 notify 判定（dirty staging → planNotify 管线）。
func (h *ChatHandler) consumeRun(cs *chatSession, events <-chan agent.Event) {
	tr := newEventTranslator(cs.AgentID)
	for ev := range events {
		for _, f := range tr.translate(ev) {
			h.pushSystem(cs.ID, f.event, f.data)
		}
	}
	h.mu.Lock()
	delete(h.runs, cs.ID)
	h.mu.Unlock()
	h.notifyIfDirty(cs)
}

// getMessages 从 EventStore 投影会话历史（重新打开会话时回填聊天内容）。
func (h *ChatHandler) getMessages(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	var evs []agent.Event
	if h.deps.Ev != nil {
		loaded, skipped, err := h.deps.Ev.LoadReport(cs.AgentID)
		if err != nil {
			writeChatErr(w, err)
			return
		}
		if skipped > 0 {
			log.Printf("chat: session %s event log skipped %d corrupt line(s)", cs.ID, skipped)
		}
		evs = loaded
	}
	msgs := projectChatHistory(evs, cs.AgentID)
	if msgs == nil {
		msgs = []chatHistoryMsg{}
	}
	writeJSON(w, msgs)
}

// abortSession 中止 AI 当前 turn（取消运行 ctx）。agent 随后发 turn/end（无 error），
// 翻译层照常推 session.status idle + session.idle，前端 busy 随之清除。
func (h *ChatHandler) abortSession(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	h.mu.RLock()
	cancel := h.runs[cs.ID]
	h.mu.RUnlock()
	if cancel != nil {
		cancel()
	}
	writeJSON(w, map[string]bool{"aborted": true})
}
