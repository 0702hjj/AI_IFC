// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// Package agent 提供进程内 Eino ADK agent loop：
// openai 组件装配（API key 空时回退确定性 scriptedModel）、
// ADK AgentEvent 翻译层、append-only JSONL 事件日志 + projection 派生消息史。
//
// 事件相关代码分散：
//   - events.go：§1 平台事件模型（9+1 种类型 + Event + 校验/序列化）· §2 EventStore
//     （append-only JSONL 事件日志）· §3 Project + BuildHistoryMessages（会话连续性阀门）
//   - adk_events.go：§4 ADK 翻译层（adk.AgentEvent → 平台 Event，见 adkTranslator）
package agent

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/cloudwego/eino/schema"
)

// ---- §1 平台事件模型 ----------------------------------------------------------

const (
	EventTurnStart        = "turn/start"
	EventTurnEnd          = "turn/end"
	EventStepStart        = "step/start"
	EventAssistantChunk   = "assistant/chunk"
	EventAssistantMessage = "assistant/message"
	EventToolCall         = "tool/call"
	EventToolResult       = "tool/result"
	EventError            = "error"
	EventSubagentStatus   = "subagent/status"
	EventQuestionAsk      = "question/ask" // HITL：模型 StatefulInterrupt 提问（M3，加法事件）
)

// Event 是事件日志与运行通道的公共载体。SubagentID/ParentSessionID 为
// subagent 派发的附加标签（additive，空 = 主会话事件，旧形状不变）：
// 父 Run 把子 agent 的全部事件打标后经同一通道上浮，EventStore 原样落盘。
type Event struct {
	Type            string          `json:"type"`
	Turn            int             `json:"turn"`
	Step            int             `json:"step,omitempty"`
	SubagentID      string          `json:"subagentId,omitempty"`
	ParentSessionID string          `json:"parentSessionId,omitempty"`
	Payload         json.RawMessage `json:"payload,omitempty"`
	Ts              time.Time       `json:"ts"`
}

var sessionIDPattern = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)

func validateSessionID(id string) error {
	if !sessionIDPattern.MatchString(id) {
		return fmt.Errorf("invalid session id %q", id)
	}
	return nil
}

// jsonPayload 序列化事件载荷；失败时返回安全兜底对象（不 panic、不产坏 JSON）。
func jsonPayload(v any) json.RawMessage {
	raw, err := json.Marshal(v)
	if err != nil {
		return json.RawMessage(`{"error":"payload marshal failed"}`)
	}
	return raw
}

// ---- §2 EventStore（append-only JSONL 事件日志） ------------------------------

// EventStore 是 append-only 的 JSONL 事件日志：{DataDir}/chat/{sessionID}.jsonl。
// 首行为 header 记录，其后每行一个 Event。所有写盘同步完成。
type EventStore struct {
	dir string
	mu  sync.Mutex
}

func NewEventStore(dataDir string) *EventStore {
	return &EventStore{dir: filepath.Join(dataDir, "chat")}
}

func (s *EventStore) path(sessionID string) string {
	return filepath.Join(s.dir, sessionID+".jsonl")
}

type headerRecord struct {
	Type      string    `json:"type"`
	Session   string    `json:"session"`
	CreatedAt time.Time `json:"created_at"`
}

func (s *EventStore) Append(sessionID string, ev Event) error {
	if err := validateSessionID(sessionID); err != nil {
		return err
	}
	if ev.ParentSessionID != "" && ev.ParentSessionID != sessionID {
		return fmt.Errorf("event parent session %q does not match log session %q", ev.ParentSessionID, sessionID)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := os.MkdirAll(s.dir, 0o755); err != nil {
		return err
	}
	path := s.path(sessionID)
	if _, err := os.Stat(path); errors.Is(err, os.ErrNotExist) {
		header, err := json.Marshal(headerRecord{Type: "header", Session: sessionID, CreatedAt: ev.Ts})
		if err != nil {
			return err
		}
		if err := os.WriteFile(path, append(header, '\n'), 0o644); err != nil {
			return err
		}
	}
	line, err := json.Marshal(ev)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(line, '\n'))
	return err
}

// Load 读出会话全部事件；坏行（截断/非 JSON）跳过，不拖垮整个会话。
func (s *EventStore) Load(sessionID string) ([]Event, error) {
	evs, _, err := s.LoadReport(sessionID)
	return evs, err
}

// LoadReport 同 Load，另返回跳过的坏行数（观测日志腐败程度）。
func (s *EventStore) LoadReport(sessionID string) (evs []Event, skipped int, err error) {
	if err := validateSessionID(sessionID); err != nil {
		return nil, 0, err
	}
	raw, err := os.ReadFile(s.path(sessionID))
	if errors.Is(err, os.ErrNotExist) {
		return nil, 0, nil
	}
	if err != nil {
		return nil, 0, err
	}
	for _, line := range strings.Split(strings.TrimSpace(string(raw)), "\n") {
		if line == "" {
			continue
		}
		var ev Event
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			skipped++
			continue
		}
		if ev.Type == "header" {
			continue
		}
		evs = append(evs, ev)
	}
	return evs, skipped, nil
}

// ---- §3 Project（事件流 → openai 风格消息投影） -------------------------------

// Project 把事件流折叠为 openai 风格的消息列表（role/content/tool_calls/tool_call_id），
// 供会话历史回填与模型上下文重建。子 agent 事件（SubagentID 非空）跳过——
// 子内容经 dispatch 工具结果回流父模型，直接注入会重复计数。
func Project(evs []Event) []map[string]any {
	var msgs []map[string]any
	for _, ev := range evs {
		if ev.SubagentID != "" {
			continue
		}
		var p map[string]any
		if len(ev.Payload) > 0 {
			if err := json.Unmarshal(ev.Payload, &p); err != nil {
				continue
			}
		}
		switch ev.Type {
		case EventTurnStart:
			msgs = append(msgs, map[string]any{"role": "user", "content": strOf(p, "user")})
		case EventAssistantMessage:
			msg := map[string]any{"role": "assistant", "content": strOf(p, "content")}
			if calls, ok := p["tool_calls"].([]any); ok && len(calls) > 0 {
				msg["tool_calls"] = calls
			}
			msgs = append(msgs, msg)
		case EventToolResult:
			msgs = append(msgs, map[string]any{
				"role":         "tool",
				"tool_call_id": strOf(p, "id"),
				"name":         strOf(p, "name"),
				"content":      strOf(p, "content"),
			})
		}
	}
	return msgs
}

func strOf(m map[string]any, key string) string {
	s, _ := m[key].(string)
	return s
}

// historyBudgetRatio 是会话记忆占模型 context 的上限比例（检查阀门阈值）。
// 未超过：历史全量喂模型（保持完整）；超过：启动语义压缩（BuildHistoryMessages 兜底）。
const historyBudgetRatio = 0.6

// BuildHistoryMessages 是会话连续性的检查阀门（跨 turn 记忆回填）：
//   - 未超预算：Project 全量折叠（user/assistant含tool_calls/tool 结果完整配对）
//   - 超过 maxContextChars*historyBudgetRatio：启动语义压缩（每 turn 只留
//     用户指令 + 最终无工具回复，从新到旧填充到预算内）——长任务/长会话不吞记忆
//
// 子 agent 事件（SubagentID 非空）跳过（子内容经 AgentAsTool 结果回流父模型）。
// 返回 []*schema.Message 供 Runner.Run 直接使用（历史 + 当前 user 由调用方拼接）。
func BuildHistoryMessages(evs []Event, maxContextChars int) []*schema.Message {
	full := projectMessages(evs)
	budget := int(float64(maxContextChars) * historyBudgetRatio)
	if messageChars(full) <= budget {
		return full // 检查阀门：未超 60%，全量喂
	}
	return compressHistoryMessages(evs, budget)
}

// projectMessages 把事件折叠为完整消息列表（与 Project 同语义，返回 schema.Message）：
// user / assistant（含 tool_calls）/ tool（tool_call_id 配对）。
func projectMessages(evs []Event) []*schema.Message {
	var msgs []*schema.Message
	for _, ev := range evs {
		if ev.SubagentID != "" {
			continue
		}
		var p map[string]any
		if len(ev.Payload) > 0 {
			if err := json.Unmarshal(ev.Payload, &p); err != nil {
				continue
			}
		}
		switch ev.Type {
		case EventTurnStart:
			msgs = append(msgs, schema.UserMessage(strOf(p, "user")))
		case EventAssistantMessage:
			content := strOf(p, "content")
			var calls []schema.ToolCall
			if raw, ok := p["tool_calls"].([]any); ok {
				for _, c := range raw {
					if cm, ok := c.(map[string]any); ok {
						fn, _ := cm["name"].(string)
						args, _ := cm["arguments"].(string)
						id, _ := cm["id"].(string)
						calls = append(calls, schema.ToolCall{
							ID:       id,
							Function: schema.FunctionCall{Name: fn, Arguments: args},
						})
					}
				}
			}
			msgs = append(msgs, schema.AssistantMessage(content, calls))
		case EventToolResult:
			msgs = append(msgs, schema.ToolMessage(
				strOf(p, "content"), strOf(p, "id"),
				schema.WithToolName(strOf(p, "name")),
			))
		}
	}
	return msgs
}

// messageChars 估算消息列表总字符数（token 近似：中文 ~1 token/字符，英文偏大——
// 用字符数作为保守上界，阀门据此判断）。
func messageChars(msgs []*schema.Message) int {
	n := 0
	for _, m := range msgs {
		if m == nil {
			continue
		}
		n += len(m.Content) + len(m.ToolCallID)
		for _, tc := range m.ToolCalls {
			n += len(tc.ID) + len(tc.Function.Name) + len(tc.Function.Arguments)
		}
	}
	return n
}

// compressHistoryMessages 是超预算时的语义压缩：按 turn 分组，
// 每 turn 压缩为 [用户指令 + 最后一条无工具调用的 assistant 回复]，
// 从新到旧填充直到预算（对话摘要，无工具调用残留，模型上下文干净）。
func compressHistoryMessages(evs []Event, budget int) []*schema.Message {
	// 按 turn 分组（子事件跳过；parentSession 子边界事件仍以 turn 为单位）
	type turn struct {
		user      string
		assistant string
	}
	var turns []turn
	var cur *turn
	for _, ev := range evs {
		if ev.SubagentID != "" {
			continue
		}
		var p map[string]any
		if len(ev.Payload) > 0 {
			if err := json.Unmarshal(ev.Payload, &p); err != nil {
				continue
			}
		}
		switch ev.Type {
		case EventTurnStart:
			turns = append(turns, turn{user: strOf(p, "user")})
			cur = &turns[len(turns)-1]
		case EventAssistantMessage:
			if cur == nil {
				continue
			}
			// 只保留最后一条无 tool_calls 的正文（中间工具调用链丢弃）
			if _, hasCalls := p["tool_calls"]; !hasCalls {
				if content := strOf(p, "content"); content != "" {
					cur.assistant = content
				}
			}
		}
	}

	// 从新到旧收集（最新优先），超预算丢最旧
	var collected [][]*schema.Message
	used := 0
	for i := len(turns) - 1; i >= 0; i-- {
		t := turns[i]
		var pair []*schema.Message
		if t.user != "" {
			pair = append(pair, schema.UserMessage(t.user))
		}
		if t.assistant != "" {
			pair = append(pair, schema.AssistantMessage(t.assistant, nil))
		}
		if len(pair) == 0 {
			continue
		}
		if used+messageChars(pair) > budget {
			break // 预算内装不下这个（更旧的）turn → 丢弃
		}
		collected = append(collected, pair)
		used += messageChars(pair)
	}
	// 反转成从旧到新（对话顺序）
	var out []*schema.Message
	for i := len(collected) - 1; i >= 0; i-- {
		out = append(out, collected[i]...)
	}
	return out
}

