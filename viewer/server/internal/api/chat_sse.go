// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj

// chat_sse.go：SSE 事件流分发（opencode /event 订阅循环、订阅管理、帧推送）。
package api

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"ifcviewer/server/internal/opencode"
)

// events 是该会话的 SSE 透传端点：浏览器 EventSource 连这里。
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
	h.mu.Unlock()
	defer func() {
		h.mu.Lock()
		delete(h.subs[cs.ID], ch)
		h.mu.Unlock()
	}()
	fmt.Fprintf(w, ": connected\n\n")
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
	h.mu.RLock()
	defer h.mu.RUnlock()
	h.pushLocked(cid, frame)
}

// forward 把一条 opencode 事件封装为 SSE 帧，定向（或广播）推给浏览器订阅者。
func (h *ChatHandler) forward(ev opencode.Event) {
	frame := []byte("event: " + ev.Type + "\ndata: " + string(ev.Properties) + "\n\n")
	ocSID := ev.SessionID()
	h.mu.RLock()
	defer h.mu.RUnlock()
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

func (h *ChatHandler) pushLocked(cid string, frame []byte) {
	for ch := range h.subs[cid] {
		select {
		case ch <- frame:
		default: // 订阅者消费不及时，丢帧保主循环
		}
	}
}
