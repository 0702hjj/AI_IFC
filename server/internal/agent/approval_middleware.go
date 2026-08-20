// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2026 0702hjj

// approval_middleware.go：D3c 交付审批 middleware（官方 approval_wrapper 形态）。
//
// 拦截「交付/落版本」类工具（save_script / deliver_plan）：调了先问——
// 首次调用 StatefulInterrupt 提问（用户经 /answer 填 AskUserInfo.UserAnswer），
// resume 后判断：确认类回答（确认/是/yes/y）→ 放行原工具执行；否则拒绝（文本返回）。
// 非目标中断（多断点）→ 重新挂起保留问题。
package agent

import (
	"context"
	"strings"

	"github.com/cloudwego/eino/adk"
	"github.com/cloudwego/eino/components/tool"
	"github.com/cloudwego/eino/schema"
)

// ApprovalState 是审批中断时保存的工具状态（恢复时判断是否已问过）。
type ApprovalState struct {
	ToolName string
	Question string
}

func init() {
	schema.Register[*ApprovalState]()
}

// approveToolNames 是审批名单（交付/落版本类工具：调了先问）。
var approveToolNames = map[string]bool{
	"save_script":  true,
	"deliver_plan": true,
}

// isApprovalAnswer 判断用户回答是否确认（确认/是/yes/y，大小写不敏感）。
func isApprovalAnswer(answer string) bool {
	switch strings.ToLower(strings.TrimSpace(answer)) {
	case "确认", "是", "yes", "y", "ok", "确定":
		return true
	}
	return false
}

// approvalMiddleware 是交付审批 middleware（挂 agent Handlers）。
type approvalMiddleware struct {
	*adk.TypedBaseChatModelAgentMiddleware[*schema.Message]
}

func newApprovalMiddleware() adk.TypedChatModelAgentMiddleware[*schema.Message] {
	return &approvalMiddleware{
		TypedBaseChatModelAgentMiddleware: &adk.TypedBaseChatModelAgentMiddleware[*schema.Message]{},
	}
}

// WrapInvokableToolCall 拦截审批名单工具：调了先问（StatefulInterrupt）→ resume 确认后放行。
func (m *approvalMiddleware) WrapInvokableToolCall(
	_ context.Context,
	endpoint adk.InvokableToolCallEndpoint,
	tCtx *adk.ToolContext,
) (adk.InvokableToolCallEndpoint, error) {
	if !approveToolNames[tCtx.Name] {
		return endpoint, nil // 非审批工具：不包装
	}
	question := "是否确认执行「" + tCtx.Name + "」？（交付/落版本为固定危险动作——请回复：确认 / 拒绝）"
	return func(ctx context.Context, args string, opts ...tool.Option) (string, error) {
		_, _, storedState := tool.GetInterruptState[*ApprovalState](ctx)
		if !isResumedWithAnswer(ctx, storedState) {
			// 首次调用 / 非目标中断：中断提问（保留原问题）
			return "", tool.StatefulInterrupt(ctx, &AskUserInfo{Question: question}, &ApprovalState{ToolName: tCtx.Name, Question: question})
		}
		isResumeTarget, hasData, data := tool.GetResumeContext[*AskUserInfo](ctx)
		if isResumeTarget && hasData {
			if isApprovalAnswer(data.UserAnswer) {
				return endpoint(ctx, args, opts...) // 用户确认 → 放行原工具
			}
			return "用户拒绝执行「" + tCtx.Name + "」（回答：" + data.UserAnswer + "）——工具未执行", nil
		}
		return "", tool.StatefulInterrupt(ctx, &AskUserInfo{Question: question}, &ApprovalState{ToolName: tCtx.Name, Question: question})
	}, nil
}

// isResumedWithAnswer 判断当前是否为「已中断 + 带用户回答」的 resume 态。
func isResumedWithAnswer(ctx context.Context, _ *ApprovalState) bool {
	isResumeTarget, hasData, _ := tool.GetResumeContext[*AskUserInfo](ctx)
	return isResumeTarget && hasData
}
