// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_sse.go：SSE 事件流分发（opencode /event 订阅循环、订阅管理、帧推送）。
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	"ifcviewer/server/internal/opencode"
)

// sseReplayBufferSize 是每会话重同步缓冲容量（最近 N 条事件）。
const sseReplayBufferSize = 64

// sseEvent 是重同步缓冲里的一条已编号 SSE 帧。
type sseEvent struct {
	id    uint64
	frame []byte
}

// events 是该会话的 SSE 透传端点：浏览器 EventSource 连这里。
// 带 Last-Event-ID 重连时，先从重同步缓冲补发 missed 事件（id 升序），再进入实时流；
// 不带 Last-Event-ID 行为与旧版一致（不补发）。缓冲已滚动（lastID 早于缓冲最早 id）时
// 从最早可用事件续传，客户端可从 id 间隙感知空洞。
func (h *ChatHandler) events(w http.ResponseWriter, r *http.Request) {
	cs := h.sessionOrErr(w, r.PathValue("cid"))
	if cs == nil {
		return
	}
	flusher, ok := w.(http.Flusher)
	if !ok {
		writeErr(w, http.StatusInternalServerError, codeInternal, "streaming unsupported")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	ch := make(chan []byte, 32)
	h.mu.Lock()
	if h.subs[cs.ID] == nil {
		h.subs[cs.ID] = map[chan []byte]struct{}{}
	}
	h.subs[cs.ID][ch] = struct{}{}
	// 注册订阅与取补发快照在同一临界区：注册后新事件只进 ch，快照只含更早事件，不重不漏。
	var missed [][]byte
	if last, err := strconv.ParseUint(r.Header.Get("Last-Event-ID"), 10, 64); err == nil {
		for _, ev := range h.evLog[cs.ID] {
			if ev.id > last {
				missed = append(missed, ev.frame)
			}
		}
	}
	h.mu.Unlock()
	defer func() {
		h.mu.Lock()
		delete(h.subs[cs.ID], ch)
		h.mu.Unlock()
	}()
	fmt.Fprintf(w, ": connected\n\n")
	for _, frame := range missed {
		if _, err := w.Write(frame); err != nil {
			return
		}
	}
	flusher.Flush()
	for {
		select {
		case data := <-ch:
			if _, err := w.Write(data); err != nil {
				return
			}
			flusher.Flush()
		case <-r.Context().Done():
			return
		}
	}
}

// dispatchLoop 全局订阅 opencode /event，断线退避重连；每条事件先过触发器（onEvent）再透传（forward）。
func (h *ChatHandler) dispatchLoop(ctx context.Context) {
	backoff := time.Second
	for {
		if ctx.Err() != nil {
			return
		}
		ch, err := h.deps.OC.Subscribe(ctx)
		if err != nil {
			log.Printf("chat: subscribe opencode events: %v (retry in %s)", err, backoff)
		} else {
			backoff = time.Second
			for ev := range ch {
				h.onEvent(ev)
				h.forward(ev)
			}
			log.Printf("chat: opencode event stream closed (retry in %s)", backoff)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
		}
		if backoff < 30*time.Second {
			backoff *= 2
		}
	}
}

// pushSystem 向指定会话的浏览器订阅者推送 chat 模块自定义 SSE 事件。
func (h *ChatHandler) pushSystem(cid, eventType string, data map[string]any) {
	raw, err := json.Marshal(data)
	if err != nil {
		return
	}
	frame := []byte("event: " + eventType + "\ndata: " + string(raw) + "\n\n")
	h.mu.Lock()
	defer h.mu.Unlock()
	h.pushLocked(cid, frame)
}

// forward 把一条 opencode 事件封装为 SSE 帧，定向（或广播）推给浏览器订阅者。
func (h *ChatHandler) forward(ev opencode.Event) {
	frame := []byte("event: " + ev.Type + "\ndata: " + string(ev.Properties) + "\n\n")
	ocSID := ev.SessionID()
	h.mu.Lock()
	defer h.mu.Unlock()
	if ocSID != "" {
		if cid, ok := h.byOC[ocSID]; ok {
			h.pushLocked(cid, frame)
			return
		}
	}
	for cid := range h.subs { // 广播（server.connected / file.edited 等无 sessionID 事件）
		h.pushLocked(cid, frame)
	}
}

// pushLocked 给帧分配会话内递增 id（SSE `id:` 行）、入重同步环形缓冲（无在线订阅者也入，
// 断线期间的事件靠它补发），再推给在线订阅者。调用方须持 h.mu 写锁。
func (h *ChatHandler) pushLocked(cid string, frame []byte) {
	if h.seq == nil { // 兼容测试手工构造的 handler
		h.seq = map[string]uint64{}
		h.evLog = map[string][]sseEvent{}
	}
	h.seq[cid]++
	frame = append([]byte("id: "+strconv.FormatUint(h.seq[cid], 10)+"\n"), frame...)
	buf := append(h.evLog[cid], sseEvent{id: h.seq[cid], frame: frame})
	if len(buf) > sseReplayBufferSize {
		buf = buf[len(buf)-sseReplayBufferSize:]
	}
	h.evLog[cid] = buf
	for ch := range h.subs[cid] {
		select {
		case ch <- frame:
		default: // 订阅者消费不及时，丢帧保主循环（重连时 Last-Event-ID 补发兜底）
		}
	}
}
