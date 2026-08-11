# W-0006: ChatSidebar 历史 fetch 覆盖 SSE 追加消息的竞态

- **状态：** done（关闭 commit：feat/v0.2-batch `fix(web): ChatSidebar 历史/SSE 合并 + EventSource 容错与重连`）
- **优先级：** P1
- **Milestone：** 待排（建议 M4 结构加固随 chat 模块一并处理）
- **来源：** W-0002 测试发现（2026-08-06）
- **执行者/分支：** opencode / feat/v0.2-batch

## 背景

`web/src/viewer/ChatSidebar.tsx:117` 初始历史 fetch resolve 时 `setMessages(history)` 为非函数式整体替换：若 SSE 事件先于历史 fetch 返回到达（慢网络/服务端推送快），SSE 已追加的消息会被历史响应整体覆盖——丢消息窗口。

## 涉及位置

- `web/src/viewer/ChatSidebar.tsx:88-121`（历史加载与 SSE 订阅的交错区）

## 方案

历史加载与 SSE 增量合并而非覆盖：函数式 setMessages（按消息 id 去重合并，历史在前、SSE 增量在后），或先完成历史加载再建立 EventSource（注意会延迟实时性，需评估）。

## 验收标准

- 构造「SSE 先到、历史后到」时序的测试：两条消息都在，无丢失
- 现有 ChatSidebar 测试（131 全绿）不回归

## 测试要求

- TDD：先写时序竞态的失败测试（W-0002 的 MockEventSource 基建可直接复用）
- 合并逻辑单测覆盖：重复 id 去重、乱序到达
