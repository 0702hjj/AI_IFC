// Package agent 提供进程内 Eino ReAct agent loop：
// openai 组件装配（API key 空时回退确定性 scriptedModel）、
// append-only JSONL 事件日志 + projection 派生消息史。
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
)

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
