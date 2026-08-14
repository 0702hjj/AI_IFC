# W-0043: Eino 替换 opencode + 主子编排（进程内 agent loop，SSE/REST 契约不变）

- **状态：** in-progress
- **优先级：** P1
- **Milestone：** v0.6（chunk E：Eino 替换 opencode + 主子编排 + web-ifc 查看器）
- **来源：** plan 2026-08-14-chunk-e-eino-webifc.md（用户裁决 2026-08-14：领域收敛工具面；主子编排一起做；本 chunk 与 web-ifc 合并为一个 PR）
- **执行者/分支：** opencode / feat/v0.9-eino-webifc

## 背景

当前 chat 走外部 `opencode serve` 子进程（`server/internal/opencode/`），工具面靠 MCP/提示词约定，无法做强类型领域工具与主子编排。chunk E 用进程内 Eino agent loop（cloudwego/eino `react.NewAgent` + `utils.InferTool` 领域工具 + callbacks 采集）全量替换 opencode，**SSE/REST 契约逐字段不变**（ChatSidebar 零改动），并落地 aibim-orchestrator 主子编排（subagent-as-tool）。参考：~/projects/work/sec-agent（Eino 最小样本）、~/projects/deepseek-harness（架构）。

## 涉及位置

- `server/internal/agent/`（新包）：model（openai 组件 / scriptedModel 回退）、agent（react 装配）、events（append-only JSONL 事件日志 + projection）、tools（领域工具集）、subagent（subagent 工具）
- `server/internal/api/`：`chat_eino.go`（7 路由 handler）、`chat_translate.go`（agent Event → opencode 形状 SSE 帧纯函数翻译层）；改造 `chat_session.go`（agentSessionId + 历史回填读事件日志 projection）
- `server/cmd/server/main.go`：装配切换（LLM 三参 config；kind 感知 client 选择，清偿 main.go:150 注释缺口）；notify 管线不动（idle 判定改 agent loop 结束事件）
- 删除：`server/internal/opencode/`、根 `opencode.json`；`.opencode/` 保留为提示词资产（README 注明不再被 server 消费）
- 文档：`docs/site/reference/ai.md`、`docs/site/development/architecture.md`、`docs/site/guide/configuration.md`、`AGENTS.md`

## 方案

1. **契约红线（逐条钉死）**：ChatSidebar 消费的 SSE 事件集与 data 形状（message.updated / message.part.updated / message.part.delta / message.part.removed / session.status / session.idle / session.error + viewer.committed / viewer.notify_failed）逐字段不变；7 条 REST 路由 + envelope + Last-Event-ID 重同步语义不变；`POST /chat/projects` 骨架项目不变；prompt 系统上下文注入格式不变。既有 chat 测试改造成新实现的契约钉（对拍）。
2. **scriptedModel**：`VIEWER_LLM_API_KEY` 为空时回退确定性 mock（sec-agent 模式）——测试与离线 demo 不依赖真模型；Eino 层全部经 scriptedModel 确定性测试。
3. **配置**：`VIEWER_LLM_API_KEY` / `VIEWER_LLM_BASE_URL` / `VIEWER_LLM_MODEL`（server_config.json 同名字段）；`VIEWER_OPENCODE_URL` 退役（config 删除 + 文档标注）。
4. **工具面（领域收敛，禁止 bash/任意文件写）**：`list_models / get_model_info / get_script / stage_script / run_script / save_script / get_versions / get_diff / get_render_entities(可选) / create_project`；文件访问只读 data 目录白名单；edit-service/cad 调用经既有 client；错误文本化供 LLM 自愈；工具结果 64KB 截断。
5. **kind 感知**：chat 绑定 dxf 模型时工具路由到 cad 服务。
6. **主子编排**：`subagent` 工具（ifc-agent/cad-agent persona，取自 `skills/aibim-orchestrator`）；子=独立 agent run + parentSessionId + 深度预算 1；子 agent 复用主工具集按 persona 过滤；子事件 SSE data 带 `subagentId`（主会话事件不带，旧形状不变），新增 `subagent.status` 事件；前端右侧边栏分组展示；子 agent staging 改动同样走 notify 管线。
7. **会话持久化**：append-only JSONL 事件日志（dsh 模式）+ projection 派生消息史；`chat-sessions.json` 映射表保留兼容。
8. **opencode 移除**：Task 6 清零 `grep -rn opencode server/ --include="*.go"` 非测试引用。
9. **VitePress 文档更新**：Eino 架构、LLM 三参、scriptedModel 离线模式、领域工具表、主子编排（Task 8）。

**显式范围外：** MAS 四级表持久化（gaia 模式）；subagent 深度 >1；bash/通用文件工具；opencode 兼容层；web-ifc 查看器（W-0044）。

## 验收标准

- 契约红线逐条满足：SSE 事件形状对拍（翻译层纯函数逐字段 + 既有 chat_sse_test 改造钉）/ 7 路由 + envelope / Last-Event-ID 重同步 / projects 骨架 / prompt 注入格式，全部不变。
- scriptedModel 离线测试：Eino 层无真模型依赖，同脚本两跑事件序列全等。
- subagent 工具 + 事件标签：子 run 事件带 `subagentId`/`parentSessionId`，`subagent.status` 下发，深度预算 1 生效，前端边栏分组渲染且主会话流不回归。
- kind 感知：dxf modelId → cad client 被调、ifc client 零调用（双 fake 钉死）。
- opencode 移除：`server/internal/opencode/`、根 `opencode.json` 删除，`VIEWER_OPENCODE_URL` 退役；`.opencode/` 保留并注明不再被 server 消费。
- VitePress AI 接入文档更新（reference/ai + architecture + configuration 中英）+ AGENTS.md 同步。
- `go test ./... && go vet ./...` 全绿（含改造成契约钉的 chat 测试）；`cd docs && npm run check:api` 无漂移（REST 形状不变）。

## 测试要求

- scriptedModel 确定性用例；react loop 工具调用回合；事件日志 append/Load round-trip + projection；MaxStep 截断。
- 翻译层逐字段对拍（含 tool part 的 state.status/title/input/output/error、reasoning 折叠段）；重同步三用例改造后红→绿；notify 触发点用例（agent loop idle + staging dirty → planNotify 顺序不变）。
- 每个领域工具：正常路径 + 错误文本化 + 64KB 截断 + kind 路由 + 路径白名单守卫。
- subagent：事件标签/parentSessionId/深度预算；ChatSidebar subagent 事件渲染用例。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）；异步写盘（JSONL append）测试用条件等待，禁止固定 sleep。
- 节奏：本项与 W-0044 同属 chunk E，整 chunk 单 PR 收口（分支 feat/v0.9-eino-webifc 累积，当天收工一次 PR）。
