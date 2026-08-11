# W-0016: AI 循环接入（脚本 diff 注入下次 prompt）

- **状态：** done
- **关闭于：** 66c3d15
- **优先级：** P1
- **Milestone：** M5 script-as-source
- **来源：** spec 2026-08-06-script-as-source-design.md（「让 AI 下一次输出看到差异」）
- **执行者/分支：** opencode / feat/script-as-source

## 背景

script-as-source 的核心收益：AI 下次介入时看到「当前脚本 + 与上一大版本的 diff」→ 增量修改而非重写。需要 chat 编排（chat_orchestrator.go）把 diff 上下文注入 prompt。

## 涉及位置

- `server/internal/api/chat_orchestrator.go`（[系统上下文] 注入点，现注入模型文件路径）
- edit-service `POST /models/{id}/script/diff`（W-0012 供给）

## 方案

1. 会话绑定模型且有 ≥2 个大版本时：orchestrator 在消息下发前拉取最近两个大版本的脚本 diff（+ PARAMS 变化摘要），以系统上下文形式注入（长度截断 4KB，超长给摘要）
2. 注入内容含纪律提示：「增量修改既有脚本，禁止重写；保持 key 稳定」
3. 不足两个版本时注入当前脚本路径（现行为保留）

## 验收标准

- 有两个大版本的会话：opencode 收到的上下文含 unified diff
- 截断逻辑正确（超长 diff 不爆 prompt）
- 无脚本模型不注入、不报错

## 测试要求

- Go 测试：mock editsvc diff 端点，断言注入内容格式/截断/无 diff 时回退
- 现有 chat 测试不回归（-race）
