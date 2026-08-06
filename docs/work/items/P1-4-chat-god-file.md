# P1-4: chat.go 上帝文件

- **状态：** done
- **关闭于：** 9766678 + 43c5014
- **优先级：** P1
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / feat/m4-hardening

## 背景

chat.go 单文件 697 行，混合了六类职责：会话管理、SSE 分发、IFC GlobalId 生成、骨架 IFC 模板、三连编排、制品归档；`ChatHandler` 持有 6 个依赖 + 4 个 map。此外 `pushLocked` 在订阅者消费慢时直接丢帧，没有重同步机制，SSE 断线重连会丢事件。

## 涉及位置

- `viewer/server/internal/api/chat.go` — 697 行上帝文件
- `chat.go:57-70` — ChatHandler 持 6 依赖 + 4 map
- `chat.go:681-688` — pushLocked 订阅者慢时丢帧，无重同步

## 方案

按职责拆为四个文件，纯代码移动、不改行为：

- `chat.go` — 路由注册 + handler 装配
- `chat_session.go` — 会话 CRUD + 幂等处理
- `chat_sse.go` — 事件流分发 + pushLocked + Last-Event-ID 重同步
- `chat_orchestrator.go` — 三连触发 + 制品归档 + 骨架 IFC 模板（含 GlobalId 生成）

同时在 SSE 重同步上补 Last-Event-ID 支持：断线重连时按客户端携带的 Last-Event-ID 续传，不再丢事件。

## 验收标准

1. `go vet` 通过，现有 chat 测试全部保持绿色。
2. SSE 断线重连不丢事件（以新增测试证明）。

## 测试要求

1. 现有 chat 测试不改断言全部通过（证明拆分无行为变化）。
2. 新增 SSE 重同步测试：客户端带 Last-Event-ID 重连，断言续传完整、无丢帧。
