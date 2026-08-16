// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// chat_translate.go：agent Event → 浏览器消费的 opencode 形状 SSE 帧的翻译层，
// 以及事件日志 → 会话历史（GET messages）的投影。无 IO；id 全部由
// (turn, step, toolCallID) 确定性派生，投影与实时流共用同一套 id 约定。
package api

import (
	"encoding/json"
	"fmt"

	"ifcviewer/server/internal/agent"
)

// translatedFrame 是一条待推送的 SSE 帧（event 名 + 可 JSON 化的 data）。
type translatedFrame struct {
	event string
	data  map[string]any
}

// --- 确定性 id 约定（实时帧与历史投影共用） ---

func userMsgID(turn int) string       { return fmt.Sprintf("msg_%d_user", turn) }
func userPartID(turn int) string      { return fmt.Sprintf("part_%d_user", turn) }
func chatMsgID(turn, step int) string { return fmt.Sprintf("msg_%d_%d", turn, step) }
func textPartID(turn, step int) string {
	return fmt.Sprintf("part_%d_%d_text", turn, step)
}
func reasonPartID(turn, step int) string {
	return fmt.Sprintf("part_%d_%d_reasoning", turn, step)
}
func toolPartID(turn, step int, callID string) string {
	if callID != "" {
		return fmt.Sprintf("part_%d_%d_tool_%s", turn, step, callID)
	}
	return fmt.Sprintf("part_%d_%d_tool", turn, step)
}

// toolState 是一个进行中的工具卡片状态（result 跨 step 到达时回填同一张卡片）。
type toolState struct {
	partID    string
	messageID string
	name      string
	input     string
}

// eventTranslator 把一个 turn 的 agent 事件流翻译为 SSE 帧序列。
// 持有 turn 内状态（part 建行去重、工具卡片配对）；按 turn 新建，不跨 turn 复用。
type eventTranslator struct {
	sessionID   string
	partStarted map[string]bool
	tools       map[string]*toolState // toolCallID（空则 name@turn@step）→ 卡片
}

func newEventTranslator(sessionID string) *eventTranslator {
	return &eventTranslator{
		sessionID:   sessionID,
		partStarted: map[string]bool{},
		tools:       map[string]*toolState{},
	}
}

func payloadMap(ev agent.Event) map[string]any {
	var p map[string]any
	if len(ev.Payload) > 0 {
		_ = json.Unmarshal(ev.Payload, &p)
	}
	if p == nil {
		p = map[string]any{}
	}
	return p
}

func strOf(p map[string]any, key string) string {
	s, _ := p[key].(string)
	return s
}

// toolKey 配对 tool/call 与 tool/result：优先 call id，空 id 退化 name@turn@step。
func toolKey(turn, step int, p map[string]any) string {
	if id := strOf(p, "id"); id != "" {
		return id
	}
	return fmt.Sprintf("%s@%d@%d", strOf(p, "name"), turn, step)
}

// translate 把一条 agent 事件翻译为 0..n 条 SSE 帧（顺序即推送顺序）。
func (tr *eventTranslator) translate(ev agent.Event) []translatedFrame {
	p := payloadMap(ev)
	switch ev.Type {
	case agent.EventTurnStart:
		return []translatedFrame{
			{event: "session.status", data: map[string]any{"status": map[string]any{"type": "busy"}}},
			{event: "message.updated", data: map[string]any{
				"info": map[string]any{"id": userMsgID(ev.Turn), "role": "user", "sessionID": tr.sessionID},
			}},
		}
	case agent.EventStepStart:
		if strOf(p, "kind") != "model" {
			return nil
		}
		return []translatedFrame{{event: "message.updated", data: map[string]any{
			"info": map[string]any{"id": chatMsgID(ev.Turn, ev.Step), "role": "assistant", "sessionID": tr.sessionID},
		}}}
	case agent.EventAssistantChunk:
		if delta := strOf(p, "content"); delta != "" {
			return tr.chunkFrames(ev, textPartID(ev.Turn, ev.Step), "text", delta)
		}
		if delta := strOf(p, "reasoning"); delta != "" {
			return tr.chunkFrames(ev, reasonPartID(ev.Turn, ev.Step), "reasoning", delta)
		}
		return nil
	case agent.EventAssistantMessage:
		content := strOf(p, "content")
		pid := textPartID(ev.Turn, ev.Step)
		if content == "" || tr.partStarted[pid] {
			return nil // 分片已建行（delta 累加），或空正文（纯 tool_calls 消息）
		}
		tr.partStarted[pid] = true
		return []translatedFrame{{event: "message.part.updated", data: map[string]any{
			"part": map[string]any{
				"id": pid, "type": "text", "messageID": chatMsgID(ev.Turn, ev.Step),
				"sessionID": tr.sessionID, "text": content,
			},
		}}}
	case agent.EventToolCall:
		name := strOf(p, "name")
		ts := &toolState{
			partID:    toolPartID(ev.Turn, ev.Step, strOf(p, "id")),
			messageID: chatMsgID(ev.Turn, ev.Step),
			name:      name,
			input:     strOf(p, "arguments"),
		}
		tr.tools[toolKey(ev.Turn, ev.Step, p)] = ts
		return []translatedFrame{{event: "message.part.updated", data: map[string]any{
			"part": tr.toolPart(ts, map[string]any{
				"status": "running", "title": name, "input": ts.input,
			}),
		}}}
	case agent.EventToolResult:
		ts := tr.tools[toolKey(ev.Turn, ev.Step, p)]
		if ts == nil { // 结果先于调用到达（日志截断等）：兜底建卡
			ts = &toolState{
				partID:    toolPartID(ev.Turn, ev.Step, strOf(p, "id")),
				messageID: chatMsgID(ev.Turn, ev.Step),
				name:      strOf(p, "name"),
			}
		}
		// 工具执行失败（error 载荷）→ 单卡错误态（status:"error" + error 字段），
		// ChatSidebar 渲染该工具卡片的 ✗ 状态（opencode 行为）；content 缺省为空。
		state := map[string]any{"title": ts.name, "input": ts.input}
		if errText := strOf(p, "error"); errText != "" {
			state["status"] = "error"
			state["error"] = errText
		} else {
			state["status"] = "completed"
			state["output"] = strOf(p, "content")
		}
		return []translatedFrame{{event: "message.part.updated", data: map[string]any{
			"part": tr.toolPart(ts, state),
		}}}
	case agent.EventError:
		return []translatedFrame{{event: "session.error", data: map[string]any{
			"error": strOf(p, "error"),
		}}}
	case agent.EventTurnEnd:
		return []translatedFrame{
			{event: "session.status", data: map[string]any{"status": map[string]any{"type": "idle"}}},
			{event: "session.idle", data: map[string]any{}},
		}
	}
	return nil
}

// chunkFrames 首个分片先建 part 行（空文本，增量走 delta），再发 delta；后续分片只发 delta。
func (tr *eventTranslator) chunkFrames(ev agent.Event, partID, partType, delta string) []translatedFrame {
	msgID := chatMsgID(ev.Turn, ev.Step)
	var frames []translatedFrame
	if !tr.partStarted[partID] {
		tr.partStarted[partID] = true
		frames = append(frames, translatedFrame{event: "message.part.updated", data: map[string]any{
			"part": map[string]any{
				"id": partID, "type": partType, "messageID": msgID,
				"sessionID": tr.sessionID, "text": "",
			},
		}})
	}
	frames = append(frames, translatedFrame{event: "message.part.delta", data: map[string]any{
		"sessionID": tr.sessionID, "messageID": msgID, "partID": partID,
		"field": "text", "delta": delta,
	}})
	return frames
}

func (tr *eventTranslator) toolPart(ts *toolState, state map[string]any) map[string]any {
	return map[string]any{
		"id": ts.partID, "type": "tool", "messageID": ts.messageID,
		"sessionID": tr.sessionID, "tool": ts.name, "state": state,
	}
}

// --- 历史回填投影 ---

// chatHistoryMsg 对齐 ChatSidebar fetchChatMessages 消费的 {info, parts} 形状。
type chatHistoryMsg struct {
	Info  map[string]any   `json:"info"`
	Parts []map[string]any `json:"parts"`
}

// projectChatHistory 把事件日志折叠为 opencode 形状的会话历史（重新打开会话时回填）。
// 与实时流共用同一套 id 约定，前端按 id 去重合并。
func projectChatHistory(evs []agent.Event, sessionID string) []chatHistoryMsg {
	var msgs []chatHistoryMsg
	msgIdx := map[string]int{}       // messageID → msgs 下标
	toolIdx := map[string][2]int{}   // toolKey → (msgIdx, partIdx)
	reasonAcc := map[string]string{} // turn/step → reasoning 累积（chunk 先于 message 到达）
	key := func(turn, step int) string { return fmt.Sprintf("%d/%d", turn, step) }

	for _, ev := range evs {
		p := payloadMap(ev)
		switch ev.Type {
		case agent.EventTurnStart:
			msgIdx[userMsgID(ev.Turn)] = len(msgs)
			msgs = append(msgs, chatHistoryMsg{
				Info: map[string]any{"id": userMsgID(ev.Turn), "role": "user", "sessionID": sessionID},
				Parts: []map[string]any{{
					"id": userPartID(ev.Turn), "type": "text", "messageID": userMsgID(ev.Turn),
					"sessionID": sessionID, "text": strOf(p, "user"),
				}},
			})
		case agent.EventAssistantChunk:
			if d := strOf(p, "reasoning"); d != "" {
				reasonAcc[key(ev.Turn, ev.Step)] += d
			}
		case agent.EventAssistantMessage:
			mid := chatMsgID(ev.Turn, ev.Step)
			var parts []map[string]any
			if r := reasonAcc[key(ev.Turn, ev.Step)]; r != "" {
				parts = append(parts, map[string]any{
					"id": reasonPartID(ev.Turn, ev.Step), "type": "reasoning",
					"messageID": mid, "sessionID": sessionID, "text": r,
				})
			}
			if c := strOf(p, "content"); c != "" {
				parts = append(parts, map[string]any{
					"id": textPartID(ev.Turn, ev.Step), "type": "text",
					"messageID": mid, "sessionID": sessionID, "text": c,
				})
			}
			msgIdx[mid] = len(msgs)
			msgs = append(msgs, chatHistoryMsg{
				Info:  map[string]any{"id": mid, "role": "assistant", "sessionID": sessionID},
				Parts: parts,
			})
		case agent.EventToolCall:
			mid := chatMsgID(ev.Turn, ev.Step)
			mi, ok := msgIdx[mid]
			if !ok {
				continue
			}
			name := strOf(p, "name")
			toolIdx[toolKey(ev.Turn, ev.Step, p)] = [2]int{mi, len(msgs[mi].Parts)}
			msgs[mi].Parts = append(msgs[mi].Parts, map[string]any{
				"id": toolPartID(ev.Turn, ev.Step, strOf(p, "id")), "type": "tool",
				"messageID": mid, "sessionID": sessionID, "tool": name,
				"state": map[string]any{
					"status": "running", "title": name, "input": strOf(p, "arguments"),
				},
			})
		case agent.EventToolResult:
			loc, ok := toolIdx[toolKey(ev.Turn, ev.Step, p)]
			if !ok {
				continue
			}
			part := msgs[loc[0]].Parts[loc[1]]
			st, _ := part["state"].(map[string]any)
			if st == nil {
				continue
			}
			if errText := strOf(p, "error"); errText != "" {
				st["status"] = "error"
				st["error"] = errText
			} else {
				st["status"] = "completed"
				st["output"] = strOf(p, "content")
			}
		}
	}
	return msgs
}
