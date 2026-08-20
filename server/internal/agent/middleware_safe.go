// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// middleware_safe.go：官方 SafeToolMiddleware 对齐实现（ch09 helpers.NewSafeToolMiddleware）。
//
// 背景：ADK 下工具返回 Go error 会中止整轮 ReAct（AgentEvent.Err → 翻译层
// session.error），违反平台契约「工具失败 = 单卡错误态 + 模型自愈」。官方做法
// 是中间件把工具 error 转成文本结果（"[tool error] %v"）交还模型，同时保留
// interrupt 类错误透传（HITL 原语不被吞）。
//
// 形状对齐 eino-examples/quickstart/chatwitheino/helpers/middleware.go：
//   - WrapInvokableToolCall / WrapStreamableToolCall 双路径
//   - compose.IsInterruptRerunError 透传（StatefulInterrupt 复用）
package agent

import (
	"context"

	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/compose"
	"github.com/cloudwego/eino/schema"
)

// toolErrPrefix 是 safeToolMiddleware 标记工具错误的文本前缀。
// 翻译层（events.go §4 adkTranslator.onTool）识别该前缀，恢复为带 error 载荷的 tool/result，
// 供前端渲染单卡错误态（契约：payload.error 非空 → status:"error"）。
const toolErrPrefix = "[tool error] "

// newSafeToolMiddleware 装配工具错误兜底 middleware（挂进 ChatModelAgent.Handlers）。
func newSafeToolMiddleware() adk.TypedChatModelAgentMiddleware[*schema.Message] {
	return &safeToolMiddleware{
		TypedBaseChatModelAgentMiddleware: &adk.TypedBaseChatModelAgentMiddleware[*schema.Message]{},
	}
}

type safeToolMiddleware struct {
	*adk.TypedBaseChatModelAgentMiddleware[*schema.Message]
}

func (m *safeToolMiddleware) WrapInvokableToolCall(
	_ context.Context,
	endpoint adk.InvokableToolCallEndpoint,
	_ *adk.ToolContext,
) (adk.InvokableToolCallEndpoint, error) {
	return func(ctx context.Context, args string, opts ...tool.Option) (string, error) {
		result, err := endpoint(ctx, args, opts...)
		if err != nil {
			if _, ok := compose.IsInterruptRerunError(err); ok {
				return "", err // HITL 中断原语透传，不文本化
			}
			return toolErrPrefix + err.Error(), nil
		}
		return result, nil
	}, nil
}

func (m *safeToolMiddleware) WrapStreamableToolCall(
	_ context.Context,
	endpoint adk.StreamableToolCallEndpoint,
	_ *adk.ToolContext,
) (adk.StreamableToolCallEndpoint, error) {
	return func(ctx context.Context, args string, opts ...tool.Option) (*schema.StreamReader[string], error) {
		sr, err := endpoint(ctx, args, opts...)
		if err != nil {
			if _, ok := compose.IsInterruptRerunError(err); ok {
				return nil, err
			}
			return singleChunkReader(toolErrPrefix + err.Error()), nil
		}
		return safeWrapReader(sr), nil
	}, nil
}

// singleChunkReader 产出单帧字符串流（对齐官方 helpers.SingleChunkReader）。
func singleChunkReader(msg string) *schema.StreamReader[string] {
	r, w := schema.Pipe[string](1)
	_ = w.Send(msg, nil)
	w.Close()
	return r
}

// safeWrapReader 代理流式工具输出；流中途错误以错误帧收尾而非中止整轮。
func safeWrapReader(sr *schema.StreamReader[string]) *schema.StreamReader[string] {
	r, w := schema.Pipe[string](64)
	go func() {
		defer w.Close()
		for {
			chunk, err := sr.Recv()
			if err != nil {
				if err.Error() == "EOF" {
					return
				}
				_ = w.Send(toolErrPrefix+err.Error(), nil)
				return
			}
			_ = w.Send(chunk, nil)
		}
	}()
	return r
}
