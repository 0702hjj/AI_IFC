# W-0002: ChatSidebar SSE 测试

- **状态：** open
- **优先级：** P1
- **Milestone：** M2（见 PLAN-v0.1.0.md）
- **来源：** PLAN-v0.1.0（M2 测试补盲）
- **执行者/分支：** （领取时填）

## 背景

`viewer/web/src/viewer/ChatSidebar.tsx`（362 行）是前端最大文件且零测试：EventSource SSE 流式渲染、会话创建/中止、消息历史、三连触发状态都在其中。P0-3 类契约问题曾因缺测试潜伏。

## 涉及位置

- `viewer/web/src/viewer/ChatSidebar.tsx`（EventSource 使用见 :121 附近）
- 测试落点：`viewer/web/src/viewer/ChatSidebar.test.tsx`
- API 层：`viewer/web/src/api/client.ts`（chat 系列方法）

## 方案

用 MockEventSource（或依赖注入 EventSource 工厂）模拟 SSE 事件流，jsdom 渲染断言。mock fetch 处理 REST 部分（sessions/messages/abort）。参照现有面板测试（DesignPanel.test.tsx 的 mock 风格）。

## 验收标准

- 覆盖：会话列表加载、发送消息（POST body 正确）、SSE text/reasoning/tool 事件流式渲染、abort、错误事件展示
- `npm test` 全绿，`npm run lint` 无新增 warning

## 测试要求

- 断言真实渲染行为（DOM 文本/状态），不断言 mock 内部
- SSE 事件按序到达与乱序/错误帧各至少一条用例
- 遵守 AGENTS.md 测试纪律 5：EventSource 异步事件用 `await screen.findBy*` 条件等待，禁止固定 sleep
