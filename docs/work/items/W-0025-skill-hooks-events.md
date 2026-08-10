# W-0025: skill hooks——校验即事件（拉→推）+ 事件 URI 化

- **状态：** done（2026-08-10，分支 feat/v0.2-script-closure，commit 7f4dad7/7de0221/0c8b6cf/61b349e，PR #28）
- **优先级：** P2
- **Milestone：** v0.2（agent 工作流加固）
- **来源：** 2026-08-08 help.md 架构精要评审（用户裁决：与 SDD 思想结合，事件驱动入约）

## 背景

aiifc skill 目前是纯被动 markdown：agent 必须**自己记得**调 `validate_script_contract`、自己记得跑沙箱——这是"主进程轮询函数返回"的拉模式，漏一步就进坏脚本。help.md 的原则是反过来：**函数结束时唤起主进程**（事件驱动闭环），与本仓 SDD 的「controller 不轮询、子代理报告即事件载荷」同构（已写入 AGENTS.md「纪律事件化」节）。

## 方案

1. **skill 包带 hooks**：`skills/aiifc/` 增加 hooks 配置（opencode / Claude Code 双形态）——agent 写入构建脚本（PostToolUse / 文件写入事件）时自动触发 `validate_script_contract` + 沙箱试跑，结果作为事件回填对话；失败即事件，不污染主上下文。
2. **打包器纳入**：`tools/skill_pack_aiifc.py` 把 hooks 文件打进归档，`tests/skill/` 加存在性校验（CI 契约）。
3. **事件 URI 化**：hook/进度事件命名规范化（`aiifc://model/{id}/script/validated` 形态），为 W-0017 多 agent 协同的事件总线打底。

## 验收标准

- agent 在支持 hooks 的环境中编辑构建脚本后，无需显式调用即收到契约校验结果事件。
- skill 包归档含 hooks；pack 测试断言。
- 不支持 hooks 的环境降级为现状（文档注明手动校验路径），不阻塞。

## 测试要求

- hooks 文件 schema 校验测试；pack 归档内容断言；降级路径文档评审。
