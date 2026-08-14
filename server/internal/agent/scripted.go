package agent

import (
	"context"
	"strings"
	"sync"

	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/schema"
)

type ToolCallSpec struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	Arguments string `json:"arguments"`
}

// ScriptStep 是 scriptedModel 的一次 Generate/Stream 产出：
// Chunks 为文本分片（Stream 逐片发帧，Generate 拼接），ToolCalls 为工具调用帧。
// 最后一步置 Repeat 时无限重复（用于 MaxStep 截断等场景）。
type ScriptStep struct {
	Chunks    []string       `json:"chunks,omitempty"`
	ToolCalls []ToolCallSpec `json:"tool_calls,omitempty"`
	Repeat    bool           `json:"repeat,omitempty"`
}

type Script struct {
	Steps []ScriptStep `json:"steps"`
}

// scriptedModel 是确定性的 ToolCallingChatModel mock：
// 每次 Generate/Stream 消费脚本下一步，同脚本两跑产出完全一致的事件序列。
type scriptedModel struct {
	mu     sync.Mutex
	script Script
	pos    int
	tools  []*schema.ToolInfo
}

func NewScriptedModel(script Script) model.ToolCallingChatModel {
	return &scriptedModel{script: script}
}

func (m *scriptedModel) WithTools(tools []*schema.ToolInfo) (model.ToolCallingChatModel, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	cp := &scriptedModel{script: m.script, pos: m.pos, tools: tools}
	return cp, nil
}

func (m *scriptedModel) nextStep() ScriptStep {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.pos < len(m.script.Steps) {
		step := m.script.Steps[m.pos]
		m.pos++
		return step
	}
	if n := len(m.script.Steps); n > 0 && m.script.Steps[n-1].Repeat {
		return m.script.Steps[n-1]
	}
	return ScriptStep{}
}

func (s ScriptStep) message() *schema.Message {
	msg := &schema.Message{Role: schema.Assistant, Content: strings.Join(s.Chunks, "")}
	for _, tc := range s.ToolCalls {
		msg.ToolCalls = append(msg.ToolCalls, schema.ToolCall{
			ID:       tc.ID,
			Type:     "function",
			Function: schema.FunctionCall{Name: tc.Name, Arguments: tc.Arguments},
		})
	}
	return msg
}

func (m *scriptedModel) Generate(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.Message, error) {
	return m.nextStep().message(), nil
}

func (m *scriptedModel) Stream(ctx context.Context, input []*schema.Message, opts ...model.Option) (*schema.StreamReader[*schema.Message], error) {
	step := m.nextStep()
	var frames []*schema.Message
	for _, chunk := range step.Chunks {
		frames = append(frames, &schema.Message{Role: schema.Assistant, Content: chunk})
	}
	if len(step.ToolCalls) > 0 {
		frames = append(frames, ScriptStep{ToolCalls: step.ToolCalls}.message())
	}
	if len(frames) == 0 {
		frames = append(frames, &schema.Message{Role: schema.Assistant})
	}
	return schema.StreamReaderFromArray(frames), nil
}
