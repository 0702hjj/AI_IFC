// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// adk_events.go：ADK AgentEvent 流 → 平台 Event 流（翻译层 2.0）。
//
// 背景：agent.go 已从 react 换到 adk.ChatModelAgent + Runner。Runner 输出的是
// adk.AgentEvent（模型/工具消息分片流），本文件把它们映射回 events.go §1 的
// 9+1 种平台事件（turn/start · step/start · assistant/chunk · assistant/message ·
// tool/call · tool/result · error · turn/end · subagent/status · question/ask），
// 保证 SSE 形状不变。
//
// 映射规则（对照官方 adk/interface.go 的 TypedMessageVariant）：
//   - Role=Assistant, IsStreaming=true   → step/start(model) + 逐帧 assistant/chunk
//     （正文/思考分片），EOF 合流 → assistant/message + 逐个 tool/call
//   - Role=Assistant, IsStreaming=false  → step/start(model) + assistant/message + tool/call
//   - Role=Tool                          → step/start(tool) + tool/result（id 取消息 ToolCallID）
//   - Err=context canceled               → 只收尾 turn/end（主动取消是正常控制流）
//   - Err=exceeds max iterations         → 错误文本化 + turn/end(error)
//   - Err 其他                           → error 事件 + turn/end(error)
//   - Action.Interrupted                 → question/ask 帧（HITL，M3；onInterrupt）
//
// 父子判定（路线 B，D10）：event.RunPath 深度 ≥2 即子 agent 事件，打
// SubagentID/ParentSessionID 标签并合成 subagent/status started/finished。
package agent

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/schema"
)
//   - Role=Tool                          → step/start(tool) + tool/result（id 取消息 ToolCallID）
//   - Err=context canceled               → 只收尾 turn/end（主动取消是正常控制流）
//   - Err=exceeds max iterations         → 错误文本化 + turn/end(error)
//   - Err 其他                           → error 事件 + turn/end(error)
//   - Action.Interrupted                 → v1 以 turn/end(error) 收尾（HITL 未接线）

// adkTranslator 把一次 ADK run 的 AgentEvent 流翻译为平台 Event 流。
// send 是唯一发送路径（agent.go 注入：EventStore 落盘 + 通道扇出）。
// agentName 是模型 step/start 事件的展示名（主 agent 默认 aiifc-main，
// 子 agent 经 WithName 覆盖——前端据此区分角色）。
//
// 父子判定（路线 B，D10）：event.RunPath 深度 ≥2 即子 agent 事件（官方
// AgentAsTool 透传，探针已验证 RunPath=[{parent} {child}]）。子事件打
// SubagentID/ParentSessionID 标签（sa_{turn}_{seq}），并合成 subagent/status
// started/finished（官方无此事件）。
type adkTranslator struct {
	turn      int
	step      int
	agentName string
	sessionID string // 父会话 id（子事件 parentSessionId 打标）
	maxStep   int
	send      func(Event)

	// 子边界状态（路线 B）：curSub 非空 = 在子 agent 事件窗口内
	subSeq     int
	curSub     string // 当前子 subagentId（sa_{turn}_{seq}）
	subName    string // 当前子 agent 名（persona 字段）
	subTask    string // 当前子任务（父 AgentAsTool tool_call 的 arguments）
	pendingArg map[string]string // 父 tool name -> arguments（task 取参）
}

func newAdkTranslator(turn int, agentName, sessionID string, maxStep int, send func(Event)) *adkTranslator {
	return &adkTranslator{
		turn: turn, agentName: agentName, sessionID: sessionID, maxStep: maxStep,
		send: send, pendingArg: map[string]string{},
	}
}

func (t *adkTranslator) emit(evType string, step int, payload map[string]any) {
	t.send(Event{Type: evType, Turn: t.turn, Step: step, Payload: jsonPayload(payload), Ts: time.Now()})
}

// emitSub 是子事件窗口内的发送：平台事件打 SubagentID/ParentSessionID 标签。
func (t *adkTranslator) emitSub(evType string, step int, payload map[string]any) {
	ev := Event{Type: evType, Turn: t.turn, Step: step, Payload: jsonPayload(payload), Ts: time.Now()}
	ev.SubagentID = t.curSub
	ev.ParentSessionID = t.sessionID
	t.send(ev)
}

// run 同步消费 ADK 事件流直至结束（Next 返回 false / 错误 / 中断），
// 并负责 turn/end 收尾。正常路径：turn/end(message=最终答复)。
// 子事件（RunPath 深度≥2）打标并合成 subagent/status 边界。
func (t *adkTranslator) run(ctx context.Context, iter *adk.AsyncIterator[*adk.AgentEvent]) {
	finalText := ""
	for {
		ev, ok := iter.Next()
		if !ok {
			break
		}
		if ev.Err != nil {
			t.zrefAbort(ctx, ev.Err)
			return
		}
		if ev.Action != nil && ev.Action.Interrupted != nil {
			// HITL（M3）：interrupt 到达 → 发 question 帧（前端弹框），不再直接收尾。
			// 模型/工具事件已先行流出；用户回答经 /answer → Agent.Resume 续跑。
			t.onInterrupt(ev.Action.Interrupted)
			return
		}
		if ev.Output == nil || ev.Output.MessageOutput == nil {
			continue
		}
		isChild := len(ev.RunPath) >= 2
		if isChild && t.curSub == "" {
			t.beginSub(ev.AgentName)
		}
		if !isChild && t.curSub != "" {
			t.endSub()
		}
		mv := ev.Output.MessageOutput
		switch mv.Role {
		case schema.Tool:
			t.onTool(mv, isChild)
		case schema.Assistant:
			if text := t.onAssistant(mv, isChild); text != "" && !isChild {
				finalText = text
			}
		}
	}
	if t.curSub != "" {
		t.endSub() // 收尾兜底（异常结束也要补 finished）
	}
	t.emit(EventTurnEnd, 0, map[string]any{"message": finalText})
}

// beginSub 进入子 agent 事件窗口：分配 subagentId 并合成 subagent/status started。
// task 取自父 AgentAsTool tool_call 的 arguments（onAssistant 已收集）。
func (t *adkTranslator) beginSub(agentName string) {
	t.subSeq++
	t.curSub = fmt.Sprintf("sa_%d_%d", t.turn, t.subSeq)
	t.subName = agentName
	t.subTask = t.pendingArg[agentName]
	t.send(Event{Type: EventSubagentStatus, Turn: t.turn, SubagentID: t.curSub, ParentSessionID: t.sessionID,
		Payload: jsonPayload(map[string]any{
			"subagentId": t.curSub, "parentSessionId": t.sessionID,
			"persona": agentName, "status": "started", "task": t.subTask,
		}), Ts: time.Now()})
}

// endSub 退出子 agent 事件窗口：合成 subagent/status finished 并清状态。
func (t *adkTranslator) endSub() {
	t.send(Event{Type: EventSubagentStatus, Turn: t.turn, SubagentID: t.curSub, ParentSessionID: t.sessionID,
		Payload: jsonPayload(map[string]any{
			"subagentId": t.curSub, "parentSessionId": t.sessionID,
			"persona": t.subName, "status": "finished", "task": t.subTask,
		}), Ts: time.Now()})
	t.curSub = ""
	t.subName = ""
	t.subTask = ""
}

// onInterrupt 处理 HITL 中断（M3）：从 InterruptContexts 找 root cause，
// 取用户可见 Info（*AskUserInfo）+ 中断 ID（resume target），发 question/ask 帧。
// turn 不在此收尾——用户回答后经 Agent.Resume 续跑（同一翻译层）。
func (t *adkTranslator) onInterrupt(info *adk.InterruptInfo) {
	if info == nil || len(info.InterruptContexts) == 0 {
		t.emit(EventTurnEnd, 0, map[string]any{"error": "agent interrupted（无中断上下文）"})
		return
	}
	// 取 root cause 中断点（最内层）
	var id string
	var question string
	for i := len(info.InterruptContexts) - 1; i >= 0; i-- {
		ic := info.InterruptContexts[i]
		if ai, ok := ic.Info.(*AskUserInfo); ok {
			id = ic.ID
			question = ai.Question
			break
		}
	}
	if id == "" || question == "" {
		t.emit(EventTurnEnd, 0, map[string]any{"error": "agent interrupted（未知 question 类型）"})
		return
	}
	t.emit(EventQuestionAsk, 0, map[string]any{
		"interruptId": id, "question": question, "checkpointId": t.sessionID,
	})
}

// zrefAbort 处理 ADK 错误事件收尾——【zref_ 前缀 = 参考保留语义，非主流程】。
// 对齐旧 react 路径 runEmitter.abortRun 的三分语义：主动取消只收尾 turn/end；
// max iterations 错误文本化；其余错误原样浮出。正常脚本下此路径不触发
// （错误收尾分支），保留官方参考价值供回归对照。
func (t *adkTranslator) zrefAbort(ctx context.Context, err error) {
	if ctx.Err() != nil || errors.Is(err, context.Canceled) || strings.Contains(err.Error(), "context canceled") {
		// 主动取消是正常控制流（前端 abort 按钮）：只发 turn/end，不刷 error 事件。
		t.emit(EventTurnEnd, 0, map[string]any{})
		return
	}
	if errors.Is(err, adk.ErrExceedMaxIterations) || strings.Contains(err.Error(), "exceeds max iterations") {
		text := fmt.Sprintf("已达最大步数限制（max step limit: %d 步），请简化任务或拆分步骤", t.maxStep)
		t.emit(EventError, 0, map[string]any{"error": text})
		t.emit(EventTurnEnd, 0, map[string]any{"error": text})
		return
	}
	text := err.Error()
	t.emit(EventError, 0, map[string]any{"error": text})
	t.emit(EventTurnEnd, 0, map[string]any{"error": text})
}

func (t *adkTranslator) onTool(mv *adk.MessageVariant, isChild bool) {
	t.step++
	step := t.step
	send := t.emit
	if isChild {
		send = t.emitSub // 子事件打 subagentId/parentSessionId 标签
	}
	send(EventStepStart, step, map[string]any{"kind": "tool", "name": mv.ToolName})
	content, id := t.toolContent(mv)
	if strings.HasPrefix(content, toolErrPrefix) {
		// safeToolMiddleware 标记的工具错误：恢复为带 error 载荷的 tool/result
		// （前端渲染单卡错误态 status:"error"，而不是整轮 session.error 横幅）。
		send(EventToolResult, step, map[string]any{
			"id": id, "name": mv.ToolName, "error": strings.TrimPrefix(content, toolErrPrefix),
		})
		return
	}
	send(EventToolResult, step, map[string]any{"id": id, "name": mv.ToolName, "content": content})
}

func (t *adkTranslator) toolContent(mv *adk.MessageVariant) (string, string) {
	if mv.IsStreaming {
		full := t.consumeStream(mv.MessageStream, -1, false) // 工具流不带 step/chunk（见 consumeStream）
		if full != nil {
			return full.Content, full.ToolCallID
		}
		return "", ""
	}
	if mv.Message != nil {
		return mv.Message.Content, mv.Message.ToolCallID
	}
	return "", ""
}

// onAssistant 处理模型输出事件（流式/非流式），返回最终正文文本。
// isChild=true 时（子 agent 事件）事件打标签；父事件同时收集 AgentAsTool
// tool_call 参数（供子边界开始时的 subagent/status task 字段）。
func (t *adkTranslator) onAssistant(mv *adk.MessageVariant, isChild bool) string {
	t.step++
	step := t.step
	send := t.emit
	if isChild {
		send = t.emitSub
	}
	send(EventStepStart, step, map[string]any{"kind": "model", "name": t.agentName})
	var full *schema.Message
	if mv.IsStreaming {
		full = t.consumeStream(mv.MessageStream, step, isChild)
	} else {
		full = mv.Message
	}
	if full == nil {
		return ""
	}
	payload := map[string]any{"content": full.Content}
	var calls []map[string]any
	for _, tc := range full.ToolCalls {
		calls = append(calls, map[string]any{
			"id": tc.ID, "name": tc.Function.Name, "arguments": tc.Function.Arguments,
		})
		if !isChild {
			// 父工具调用参数收集（AgentAsTool 子任务 = arguments）
			t.pendingArg[tc.Function.Name] = tc.Function.Arguments
		}
	}
	if len(calls) > 0 {
		payload["tool_calls"] = calls
	}
	send(EventAssistantMessage, step, payload)
	for _, tc := range full.ToolCalls {
		send(EventToolCall, step, map[string]any{
			"id": tc.ID, "name": tc.Function.Name, "arguments": tc.Function.Arguments,
		})
	}
	return full.Content
}

// consumeStream 消费一条消息流：正文/思考分片逐帧发 assistant/chunk（仅模型流，
// step>0 时）；EOF 后 ConcatMessages 合流为完整消息。step<=0（工具流）只排空合流。
func (t *adkTranslator) consumeStream(stream *schema.StreamReader[*schema.Message], step int, isChild bool) *schema.Message {
	if stream == nil {
		return nil
	}
	stream.SetAutomaticClose()
	send := t.emit
	if isChild {
		send = t.emitSub
	}
	var frames []*schema.Message
	for {
		frame, err := stream.Recv()
		if err != nil {
			break // io.EOF 或流错误：以已收帧收尾（ADK 流错误不打断整轮）
		}
		if frame == nil {
			continue
		}
		frames = append(frames, frame)
		if step <= 0 {
			continue
		}
		if frame.Content != "" {
			send(EventAssistantChunk, step, map[string]any{"content": frame.Content})
		}
		if frame.ReasoningContent != "" {
			send(EventAssistantChunk, step, map[string]any{"reasoning": frame.ReasoningContent})
		}
	}
	if len(frames) == 0 {
		return nil
	}
	full, err := schema.ConcatMessages(frames)
	if err != nil {
		return frames[len(frames)-1] // 合流失败退化：以最后一帧为准（不拖垮整轮）
	}
	return full
}
