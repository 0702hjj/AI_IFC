# W-0007: ChatSidebar 未处理 EventSource 原生 error 与非法帧

- **状态：** in-progress
- **优先级：** P2
- **Milestone：** 待排（建议随 W-0006 一并处理）
- **来源：** W-0002 测试发现（2026-08-06）
- **执行者/分支：** opencode / feat/v0.2-batch

## 背景

`viewer/web/src/viewer/ChatSidebar.tsx` 只监听业务事件（:123-214），未监听 EventSource 原生 `error`：SSE 断连无 UI 反馈；事件帧为非法 JSON 时 `JSON.parse` 在回调内抛出，无容错。与 P1-4（chat.go SSE 无重同步）属同一可靠性面。

## 涉及位置

- `viewer/web/src/viewer/ChatSidebar.tsx:121-214`

## 方案

1. EventSource 监听 `error`：断连提示 + 自动重连（EventSource 原生会重连，UI 显示连接状态即可）
2. 事件回调内 JSON.parse 包 try/catch：非法帧跳过并计数/提示，不中断流
3. 与 P1-4 的 SSE 重同步（Last-Event-ID）设计对齐，避免两边各做一套

## 验收标准

- 断连时 UI 有连接状态提示，重连后恢复
- 注入非法 JSON 帧：流不中断、后续正常帧仍渲染

## 测试要求

- 非法帧用例（修复后应有）：帧被跳过、流继续
- 断连→重连用例：UI 状态变化断言
