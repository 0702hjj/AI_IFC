package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/cloudwego/eino/callbacks"
	"github.com/cloudwego/eino/components"
	"github.com/cloudwego/eino/components/model"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/flow/agent"
	"github.com/cloudwego/eino/flow/agent/react"
	"github.com/cloudwego/eino/schema"
)

const defaultPersona = `你是 AI_IFC 平台的内置智能体，帮助设计师通过对话完成 IFC/CAD 模型的生成与修改。
工作方式：理解用户意图后调用领域工具（脚本暂存/沙箱执行/版本保存等）推进任务，每一步说明依据。`

const defaultMaxStep = 20

type Option func(*agentOptions)

type agentOptions struct {
	model   model.ToolCallingChatModel
	tools   []tool.BaseTool
	persona string
	maxStep int
	store   *EventStore
}

func WithModel(m model.ToolCallingChatModel) Option {
	return func(o *agentOptions) { o.model = m }
}

func WithTools(tools []tool.BaseTool) Option {
	return func(o *agentOptions) { o.tools = tools }
}

func WithPersona(persona string) Option {
	return func(o *agentOptions) { o.persona = persona }
}

func WithMaxStep(n int) Option {
	return func(o *agentOptions) { o.maxStep = n }
}

func WithStore(s *EventStore) Option {
	return func(o *agentOptions) { o.store = s }
}

type Agent struct {
	react *react.Agent
	store *EventStore
}

// New 装配 react.NewAgent：cfg.APIKey 为空（且未注入 WithModel）时回退确定性
// scriptedModel，离线 demo 与测试不依赖真模型。
func New(cfg LLMConfig, opts ...Option) (*Agent, error) {
	o := agentOptions{persona: defaultPersona, maxStep: defaultMaxStep}
	for _, opt := range opts {
		opt(&o)
	}
	cm := o.model
	if cm == nil {
		var err error
		cm, err = NewChatModel(context.Background(), cfg)
		if err != nil {
			return nil, fmt.Errorf("create chat model: %w", err)
		}
		if cm == nil {
			cm = defaultScriptedModel()
		}
	}
	r, err := react.NewAgent(context.Background(), &react.AgentConfig{
		ToolCallingModel: cm,
		ToolsConfig:      compose.ToolsNodeConfig{Tools: o.tools},
		MessageModifier:  react.NewPersonaModifier(o.persona),
		MaxStep:          o.maxStep,
	})
	if err != nil {
		return nil, fmt.Errorf("create react agent: %w", err)
	}
	return &Agent{react: r, store: o.store}, nil
}

// Run 执行一轮 ReAct 循环，返回只读事件通道（循环结束即关闭）。
// 事件同时扇出到通道与 EventStore（append-only JSONL）；Ts 在扇出时打戳。
func (a *Agent) Run(ctx context.Context, sessionID, userText string) (<-chan Event, error) {
	if err := validateSessionID(sessionID); err != nil {
		return nil, err
	}
	turn := 1
	if a.store != nil {
		prev, err := a.store.Load(sessionID)
		if err != nil {
			return nil, fmt.Errorf("load session %s: %w", sessionID, err)
		}
		for _, ev := range prev {
			if ev.Type == EventTurnStart {
				turn++
			}
		}
	}

	out := make(chan Event, 256)
	em := &runEmitter{turn: turn, pending: map[string][]string{}}
	em.emit = func(evType string, step int, payload map[string]any) {
		ev := Event{Type: evType, Turn: turn, Step: step, Payload: jsonPayload(payload), Ts: time.Now()}
		if a.store != nil {
			_ = a.store.Append(sessionID, ev)
		}
		select {
		case out <- ev:
		case <-ctx.Done():
		}
	}

	go func() {
		defer close(out)
		em.emit(EventTurnStart, 0, map[string]any{"user": userText})
		msg, err := a.react.Generate(ctx,
			[]*schema.Message{schema.UserMessage(userText)},
			agent.WithComposeOptions(compose.WithCallbacks(em.handler())))
		if err != nil {
			em.emit(EventError, 0, map[string]any{"error": err.Error()})
			em.emit(EventTurnEnd, 0, map[string]any{"error": err.Error()})
			return
		}
		em.emit(EventTurnEnd, 0, map[string]any{"message": msg.Content})
	}()
	return out, nil
}

func jsonPayload(v any) json.RawMessage {
	raw, err := json.Marshal(v)
	if err != nil {
		return json.RawMessage(`{"error":"payload marshal failed"}`)
	}
	return raw
}

// runEmitter 经 eino callbacks 观测模型/工具每一步并扇出为事件（trace 模式）。
type runEmitter struct {
	turn int

	mu      sync.Mutex
	step    int
	pending map[string][]string // tool name -> 待配对 tool_call id 队列

	emit func(evType string, step int, payload map[string]any)
}

func (e *runEmitter) handler() callbacks.Handler {
	return callbacks.NewHandlerBuilder().
		OnStartFn(e.onStart).
		OnEndFn(e.onEnd).
		OnErrorFn(e.onError).
		Build()
}

func kindOf(info *callbacks.RunInfo) string {
	switch info.Component {
	case components.ComponentOfChatModel:
		return "model"
	case components.ComponentOfTool:
		return "tool"
	default:
		return ""
	}
}

func (e *runEmitter) onStart(ctx context.Context, info *callbacks.RunInfo, input callbacks.CallbackInput) context.Context {
	kind := kindOf(info)
	if kind == "" {
		return ctx
	}
	e.mu.Lock()
	e.step++
	step := e.step
	e.mu.Unlock()
	e.emit(EventStepStart, step, map[string]any{"kind": kind, "name": info.Name})
	return ctx
}

func (e *runEmitter) onEnd(ctx context.Context, info *callbacks.RunInfo, output callbacks.CallbackOutput) context.Context {
	switch kindOf(info) {
	case "model":
		switch out := output.(type) {
		case *schema.Message:
			e.onModelEnd(out)
		case *model.CallbackOutput:
			e.onModelEnd(out.Message)
		}
	case "tool":
		switch out := output.(type) {
		case string:
			e.onToolEnd(info.Name, out)
		case *tool.CallbackOutput:
			e.onToolEnd(info.Name, out.Response)
		}
	}
	return ctx
}

func (e *runEmitter) onModelEnd(msg *schema.Message) {
	if msg == nil {
		return
	}
	e.mu.Lock()
	step := e.step
	var calls []map[string]any
	for _, tc := range msg.ToolCalls {
		calls = append(calls, map[string]any{
			"id": tc.ID, "name": tc.Function.Name, "arguments": tc.Function.Arguments,
		})
		e.pending[tc.Function.Name] = append(e.pending[tc.Function.Name], tc.ID)
	}
	e.mu.Unlock()

	payload := map[string]any{"content": msg.Content}
	if len(calls) > 0 {
		payload["tool_calls"] = calls
	}
	e.emit(EventAssistantMessage, step, payload)
	for _, tc := range msg.ToolCalls {
		e.emit(EventToolCall, step, map[string]any{
			"id": tc.ID, "name": tc.Function.Name, "arguments": tc.Function.Arguments,
		})
	}
}

func (e *runEmitter) onToolEnd(name, response string) {
	e.mu.Lock()
	step := e.step
	id := ""
	if q := e.pending[name]; len(q) > 0 {
		id = q[0]
		e.pending[name] = q[1:]
	}
	e.mu.Unlock()
	e.emit(EventToolResult, step, map[string]any{"id": id, "name": name, "content": response})
}

func (e *runEmitter) onError(ctx context.Context, info *callbacks.RunInfo, err error) context.Context {
	if kindOf(info) == "" {
		return ctx
	}
	e.mu.Lock()
	step := e.step
	e.mu.Unlock()
	e.emit(EventError, step, map[string]any{"error": err.Error(), "name": info.Name})
	return ctx
}
