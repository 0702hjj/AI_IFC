# W-0055: 本地 GUI 调试 agent 快速工具（收编/固化本地调试手段）

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.13（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-21 用户裁决：「以及本地有个在GUI调试agent的快速工具，分开提」
- **执行者/分支：** （领取时填）

## 背景

agent 调试目前依赖本地手工手段（起 server → curl chat 端点 / 前端 ChatSidebar 对话 / 看日志），没有一个「GUI 调试 agent」的快速工具收编进仓库。用户提到「本地有个在 GUI 调试 agent 的快速工具」——需要把它**固化/收编**成仓库内可复用工具，让调试 agent（scriptedModel 确定性 / 真实 LLM / SSE 帧序列 / 工具调用轨迹）有可视化 GUI，而非每次靠 curl + 日志。

**现状痛点**：
- 调试 chat agent 要起整套 server + 前端，看 SSE 帧要 curl 或抓包；
- scriptedModel 是确定性 mock——但它的「预期脚本序列」没有可视化编辑/回放工具；
- 工具调用轨迹（哪个 agent 调了哪个 tool、产物落哪）没有 GUI 视图，只能看日志 grep；
- 子事件标签（sa_{turn}_{seq}）、subagent/status 合成、中断/恢复（ask_user）的调试靠人肉推。

## 涉及位置

- 新增 `tools/` 下调试工具（GUI 形态待定：web 小工具 or 复用前端 ChatSidebar or 独立 html）
- `server/internal/agent/events.go`（事件翻译——GUI 展示的事件源）
- `server/internal/agent/`（scriptedModel 的脚本序列可编辑）
- `server/internal/api/chat.go`（SSE 端点——GUI 接）
- `docs/work/items/W-0051`（流程对齐审查——GUI 工具可辅助）

## 方案

1. **形态决策**：GUI 调试工具用哪种形态——
   a. 独立 web 小工具（`tools/agent-debug/`，起 vite/静态页，接 chat SSE + 事件流）；
   b. 复用前端 ChatSidebar + 调试面板（dev 模式开关）；
   c. 纯本地 CLI 补 SSE 可视化（hurl + 渲染）。
   倾向 a（独立、不污染主前端、可复用 api_regulation 契约）。
2. **核心能力**：
   - 对话驱动（scriptedModel / 真实 LLM 可选）；
   - SSE 帧序列可视化（按事件 kind 着色、子事件边界、错误文本化截断提示）；
   - 工具调用轨迹（时间线：哪个 agent 调 tool、参数、产物路径）；
   - ask_user 中断/恢复模拟（answer 端点）。
3. **确定性回放**：scriptedModel 的脚本序列可编辑/保存/回放（回归用）。

## 验收标准

- GUI 工具可用：起 server 后一条命令打开 GUI，能选 scriptedModel/真实 LLM 跑对话，SSE 帧序列 + 工具轨迹可见。
- 工具调用轨迹可视化：能看清 plan→cad→ifc 各环节的 tool 调用与产物落盘。
- ask_user 中断/恢复可在 GUI 里操作。
- 工具收编进仓库（tools/agent-debug/ 或等价位置），README 说明启动方式。

## 测试要求

- 若为独立 web 工具：至少组件级测试（vitest）。
- 不要求（工具性质）——但 scriptedModel 回放若复用事件翻译层，不得破坏现有契约测试。
- 测试量 ≥ 实现量。
