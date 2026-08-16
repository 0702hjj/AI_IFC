# .opencode/ —— 提示词资产（存档）

本目录是 **prompt 资产存档**，自 chunk E（2026-08）起 **不再被 server 消费**：
对话链路已由进程内 Eino agent 全面接管（`server/internal/agent/`），
`opencode serve` 客户端（`server/internal/opencode/`）、根 `opencode.json` 与
`VIEWER_OPENCODE_URL` 配置均已退役删除。

- `agent/ifc-demo.md`、`agent/viewer-opencode-integration.md`：demo 时代的
  opencode agent 提示词定义，保留作 Eino persona（`agent.OrchestratorPersona`）
  与领域工具集演化的参考素材；SSE 帧形状的翻译契约见
  `server/internal/api/chat_translate.go`（浏览器契约 `opencodeSessionId`
  字段名亦保留，web client.ts 不动）。
- `package.json` / `node_modules/`：`@opencode-ai/plugin` 的历史依赖，
  已 gitignore，仅本地残留。
