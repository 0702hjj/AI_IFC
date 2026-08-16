package agent

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"strings"
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

编辑纪律（script-as-source：脚本是模型的唯一事实源，改模型 = 改脚本）：
- 先 get_script 读当前脚本，在既有脚本上做增量修改，禁止整体重写。
- 变更走 stage_script → run_script（沙箱验证）→ save_script（落大版本）三段式；run 失败先读错误改脚本再重试。
- 保持 PARAMS 的 key 稳定：只改值或新增 key，不改既有 key 名；设计意图优先用 PARAMS 参数化表达。
IFC 与 DXF 模型走同一套工具（后端按 kind 自动路由），每一步说明依据。`

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

// Run 执行一轮 ReAct 循环（Stream 路径），返回只读事件通道（循环结束即关闭）。
// 事件同时扇出到通道与 EventStore（append-only JSONL）；Ts 在扇出时打戳。
// EventStore 写盘失败不静默——以 error 事件浮出到通道，循环本身不被打断。
//
// 事件顺序确定性设计：react 输出流只带最终答复分片，中间模型/工具消息经
// eino callbacks 观测（graph 线程同步发 step/start、tool/result；模型流式输出
// 由消费 goroutine 合流为 assistant/message + tool/call 并逐片发 chunk）。
// graph 线程在每个组件 onStart 先等上一模型流的消费完成信号（done），
// 主 goroutine 在收尾前等最后一个 done——两条执行线的相对顺序由此确定。
// 调用方必须排空通道直至关闭（缓冲 256，无人消费会阻塞）。
func (a *Agent) Run(ctx context.Context, sessionID, userText string) (<-chan Event, error) {
	if err := validateSessionID(sessionID); err != nil {
		return nil, err
	}
	ctx = WithSessionID(ctx, sessionID) // 工具经 SessionIDFromContext 解析会话绑定模型
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
	send := func(force bool, evType string, step int, payload map[string]any) {
		em.mu.RLock()
		defer em.mu.RUnlock()
		if em.closed && !force { // 主 goroutine 已收尾：迟到的 callback/合流事件丢弃（不得 send on closed）
			return
		}
		ev := Event{Type: evType, Turn: turn, Step: step, Payload: jsonPayload(payload), Ts: time.Now()}
		if a.store != nil {
			if err := a.store.Append(sessionID, ev); err != nil && evType != EventError {
				out <- Event{Type: EventError, Turn: turn, Step: step, Ts: time.Now(),
					Payload: jsonPayload(map[string]any{"error": "event store append: " + err.Error()})}
			}
		}
		out <- ev
	}
	em.emit = func(evType string, step int, payload map[string]any) {
		send(false, evType, step, payload)
	}
	// forceEmit 收尾专用：closed 置位后仍发（仅主 goroutine 的 error/turn/end 兜底帧）。
	forceEmit := func(evType string, payload map[string]any) {
		send(true, evType, 0, payload)
	}

	go func() {
		em.emit(EventTurnStart, 0, map[string]any{"user": userText})
		sr, err := a.react.Stream(ctx,
			[]*schema.Message{schema.UserMessage(userText)},
			agent.WithComposeOptions(compose.WithCallbacks(em.handler())))
		if err != nil {
			em.abortRun(ctx, out, forceEmit, err)
			return
		}
		defer sr.Close()
		for {
			if _, err := sr.Recv(); err != nil {
				if !errors.Is(err, io.EOF) {
					em.waitLastModel(ctx)
					em.abortRun(ctx, out, forceEmit, err)
					return
				}
				break
			}
		}
		final := em.waitLastModel(ctx)
		msg := ""
		if final != nil {
			msg = final.Content
		}
		em.emit(EventTurnEnd, 0, map[string]any{"message": msg})
		em.finishRun(out)
	}()
	return out, nil
}

// finishRun 正常收尾：置 closed（挡掉迟到 emit）→ 等合流 goroutine 退出 → 关通道。
// emit 持 RLock 发送、closed 置位持 Lock，close 与 send 之间有 happens-before。
func (e *runEmitter) finishRun(out chan Event) {
	e.mu.Lock()
	e.closed = true
	e.mu.Unlock()
	e.wg.Wait()
	close(out)
}

// abortRun 异常/取消收尾：先置 closed（截断路径上迟到的合流事件确定丢弃），
// 再补 error/turn/end 兜底帧（force），最后等合流 goroutine 退出、关通道。
// 主动取消（abort）是正常控制流，只发 turn/end；组件 onError 已上报的同一错误不重复。
func (e *runEmitter) abortRun(ctx context.Context, out chan Event, forceEmit func(string, map[string]any), err error) {
	e.mu.Lock()
	e.closed = true
	// 包裹去重：eino 把组件错误再包一层（[NodeRunError] … [LocalFunc] … node path），
	// 精确相等匹配不到已上报的错误——改包含判定，工具/模型级已上报（工具错误走
	// tool/result 单卡映射）的错误不再重复刷 session 级 error 事件。
	seen := e.lastErr != "" && strings.Contains(err.Error(), e.lastErr)
	e.mu.Unlock()
	if ctx.Err() == nil && !errors.Is(err, context.Canceled) {
		if !seen {
			forceEmit(EventError, map[string]any{"error": err.Error()})
		}
		forceEmit(EventTurnEnd, map[string]any{"error": err.Error()})
	} else {
		forceEmit(EventTurnEnd, map[string]any{})
	}
	e.wg.Wait()
	close(out)
}

func jsonPayload(v any) json.RawMessage {
	raw, err := json.Marshal(v)
	if err != nil {
		return json.RawMessage(`{"error":"payload marshal failed"}`)
	}
	return raw
}

// modelDone 是一个模型步骤的完成信号：在 onStart(model) 即注册（错误路径也能等到），
// 由流式输出消费 goroutine（onEndStream）或 onError 关闭（once 保证只关一次）；
// 关闭时该步骤的 chunk/assistant/message/tool/call 事件已全部发出；final 携带合流后的完整消息。
type modelDone struct {
	ch    chan struct{}
	once  sync.Once
	final *schema.Message
}

func (d *modelDone) close() { d.once.Do(func() { close(d.ch) }) }

// runEmitter 经 eino callbacks 观测模型/工具每一步并扇出为事件（trace 模式）。
// closed/wg 与主 goroutine 的收尾配合，保证 close(out) 后无任何 send。
type runEmitter struct {
	turn int

	mu        sync.RWMutex
	step      int
	modelStep int                 // 当前模型组件的 step 序号
	prevModel *modelDone          // 上一模型步骤的消费完成信号（待等待）
	pending   map[string][]string // tool name -> 待配对 tool_call id 队列
	wg        sync.WaitGroup      // 模型流合流 goroutine
	closed    bool                // 主 goroutine 已收尾（后续 emit 丢弃）
	lastErr   string              // onError 已上报的错误（finishRun 去重）
	emit      func(evType string, step int, payload map[string]any)
}

func (e *runEmitter) handler() callbacks.Handler {
	return callbacks.NewHandlerBuilder().
		OnStartFn(e.onStart).
		OnEndFn(e.onEnd).
		OnErrorFn(e.onError).
		OnEndWithStreamOutputFn(e.onEndStream).
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

// waitPrevModel 在 graph 线程内等待上一模型步骤的消费 goroutine 完成，
// 保证 assistant/message、tool/call 先于后续组件的 step/start 落序列。
func (e *runEmitter) waitPrevModel() {
	e.mu.Lock()
	prev := e.prevModel
	e.prevModel = nil
	e.mu.Unlock()
	if prev != nil {
		<-prev.ch
	}
}

// waitLastModel 等最后一个模型步骤消费完成（主 goroutine 收尾前调用），
// 返回合流后的最终答复消息。graph 中止时框架会关闭流拷贝，消费 goroutine
// 随之 EOF，故此处无条件等待不会死锁。
func (e *runEmitter) waitLastModel(ctx context.Context) *schema.Message {
	e.mu.Lock()
	prev := e.prevModel
	e.prevModel = nil
	e.mu.Unlock()
	if prev == nil {
		return nil
	}
	select {
	case <-prev.ch:
		return prev.final
	case <-ctx.Done(): // 取消路径：框架未必投递流式回调，兜底防挂（迟到事件由 closed 挡掉）
		return nil
	}
}

func (e *runEmitter) onStart(ctx context.Context, info *callbacks.RunInfo, input callbacks.CallbackInput) context.Context {
	kind := kindOf(info)
	if kind == "" {
		return ctx
	}
	e.waitPrevModel() // 模型流已被 graph 消费完（工具调用已集齐），此处仅等消费 goroutine 被调度
	e.mu.Lock()
	e.step++
	step := e.step
	if kind == "model" {
		e.modelStep = step
		e.prevModel = &modelDone{ch: make(chan struct{})} // 即时注册：错误/截断路径也能等到本步骤收尾
	}
	e.mu.Unlock()
	e.emit(EventStepStart, step, map[string]any{"kind": kind, "name": info.Name})
	return ctx
}

func (e *runEmitter) onEnd(ctx context.Context, info *callbacks.RunInfo, output callbacks.CallbackOutput) context.Context {
	if kindOf(info) != "tool" {
		return ctx
	}
	switch out := output.(type) {
	case string:
		e.onToolEnd(info.Name, out)
	case *tool.CallbackOutput:
		e.onToolEnd(info.Name, out.Response)
	}
	return ctx
}

// onEndStream 观测模型组件的流式输出：起消费 goroutine 逐帧读——
// 正文/思考分片即发 chunk 事件（浏览器流式渲染），EOF 后合流为
// assistant/message + tool/call 并关闭 done 信号。非模型组件的流只排空。
func (e *runEmitter) onEndStream(ctx context.Context, info *callbacks.RunInfo, output *schema.StreamReader[callbacks.CallbackOutput]) context.Context {
	if kindOf(info) != "model" {
		go func() {
			defer output.Close()
			for {
				if _, err := output.Recv(); err != nil {
					return
				}
			}
		}()
		return ctx
	}
	e.mu.Lock()
	if e.closed { // 迟到的流式回调（取消路径）：只排空，不产事件
		e.mu.Unlock()
		go func() {
			defer output.Close()
			for {
				if _, err := output.Recv(); err != nil {
					return
				}
			}
		}()
		return ctx
	}
	step := e.modelStep
	done := e.prevModel // onStart(model) 已注册
	if done == nil {    // 防御：回调乱序时自建（本步骤事件无人等待，仅保证不丢）
		done = &modelDone{ch: make(chan struct{})}
		e.prevModel = done
	}
	e.wg.Add(1)
	e.mu.Unlock()
	go func() {
		defer e.wg.Done()
		defer done.close()
		defer output.Close()
		var frames []*schema.Message
		for {
			frame, err := output.Recv()
			if err != nil {
				break
			}
			msg, ok := frame.(*schema.Message)
			if !ok || msg == nil {
				continue
			}
			frames = append(frames, msg)
			if msg.Content != "" {
				e.emit(EventAssistantChunk, step, map[string]any{"content": msg.Content})
			}
			if msg.ReasoningContent != "" {
				e.emit(EventAssistantChunk, step, map[string]any{"reasoning": msg.ReasoningContent})
			}
		}
		if len(frames) > 0 {
			if full, err := schema.ConcatMessages(frames); err == nil {
				done.final = full
				e.onModelEnd(step, full)
			}
		}
	}()
	return ctx
}

func (e *runEmitter) onModelEnd(step int, msg *schema.Message) {
	if msg == nil {
		return
	}
	e.mu.Lock()
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
	kind := kindOf(info)
	if kind == "" {
		return ctx
	}
	e.mu.Lock()
	step := e.step
	if kind == "model" && e.prevModel != nil {
		e.prevModel.close() // 模型未产出流式输出即失败：释放等待方
	}
	e.lastErr = err.Error() // 去重：abortRun 不再为同一错误补 session 级 error 事件
	toolID := ""
	if kind == "tool" { // 配对待回卡片的 tool_call id（同 onToolEnd）
		if q := e.pending[info.Name]; len(q) > 0 {
			toolID = q[0]
			e.pending[info.Name] = q[1:]
		}
	}
	e.mu.Unlock()
	if ctx.Err() != nil || errors.Is(err, context.Canceled) {
		return ctx // 主动取消不刷 error 事件（abort 是正常控制流）
	}
	if kind == "tool" {
		// 工具执行失败 → 带 error 载荷的 tool/result：前端渲染该工具卡片的错误态
		// （input/error 字段），而不是只有整轮失败的 session.error 横幅。
		e.emit(EventToolResult, step, map[string]any{"id": toolID, "name": info.Name, "error": err.Error()})
		return ctx
	}
	e.emit(EventError, step, map[string]any{"error": err.Error(), "name": info.Name})
	return ctx
}
