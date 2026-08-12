# PLAN v0.1.0：从审计到发布

> 来源：AUDIT-2026-08-05 的四步方案 + 原 `docs/internal/open-source-plan.md`（2026-07-30）仍有效的执行细节。
> 目标：修掉 P0 → 补齐测试 → Docker Compose 一键部署 + v0.1.0 发布 → 结构加固与 SCAD 遗产收编。

> 四步执行方案（2026-08-05 评估）与 milestone 一一对应：第 0 步修复冲刺 = M1；第 1 步测试补盲 = M2；第 2 步发布化（roadmap 近期项）= M3；第 3 步结构性加固 + 第 4 步仓库身份收编 = M4。

## Milestone 总览

| M | 名称 | 包含工作项 | 完成判据 |
|---|---|---|---|
| M1 | 修复冲刺 ✅（PR #10，2026-08-06）| P0-1, P0-2, P0-3, P0-4, P2-3, P2-9, P2-10 | 全部 done，CI 绿 |
| M2 | 测试补盲 ✅（PR #13，2026-08-06）| P1-5, W-0001, W-0002, W-0003 | 新增测试合入，PG job 在 CI 运行 |
| M3 | 发布化 ✅（PR #15，2026-08-06）| W-0004, W-0005, P2-7 | `docker compose up` 一键起，v0.1.0 tag + Release |
| M4 | 结构加固 + 身份收编 ✅（PR #17，2026-08-06）| P1-1, P1-2, P1-3, P1-4, P2-1, P2-8 | 全部 done，SCAD 遗产收编决策落地（移出至 SimpleCADAPI-archive） |
| M5 | script-as-source 转向 ✅（2026-08-07，spec: 2026-08-06-script-as-source-design.md）| W-0011..W-0016 | 脚本为唯一事实源；diff 三层×两级；PARAMS 表单 + 脚本下钻；沙箱执行；design JSON 下线 |
| v0.2 | script-closure 收口 ✅（2026-08-10，分支 feat/v0.2-script-closure）| W-0021..W-0025 | 直改退役残留消费者收口（notify 走 script 管线）；params_keys 定位聚焦；骨架确定性；校验隔离机器强制；skill hooks 校验即事件 |
| v0.3 | orchestrator-closure ✅（2026-08-11，分支 feat/v0.2-orchestrator-closure）| W-0017 spec + notify 事件化 + minors 清扫 + 平台框架入约 | notify 重构为 Pure Core + Imperative Shell；事件 URI 化闭环；架构方向定稿入约 |
| v0.4 | 可复用性 + 上线健壮性 ✅（2026-08-11，分支 feat/v0.2-orchestrator-closure，PR 待提）| 物理重组（viewer/ 拆分）+ Go OpenAPI + skill 打包器泛化 + services/ifc 独立调用文档 + diff 超时 + 重转去重 + stale 清扫 | 结构一步到位（services/ifc + web/server/converter/mcp 顶层化 + skills/aidxfv 收敛）；对外唯一入口机器可消费 OpenAPI；任意 skill 可打包；diff 超时 504；同源跳过重转 |
| v0.5 | 可移植复用（spec: 2026-08-12-portability-reuse-design.md，分支 feat/v0.5-portability-reuse）| W-0026..W-0029（W-0030 仅立项） | 对接契约入站；services/ifc 镜像冒烟通过；skill 版本化 + Release 流程走通；aibim-orchestrator 提示词包可打包、W-0017 关闭 |

## M1 修复冲刺（建议分支 `fix/post-v2-audit`）

顺序：每个 P0 先实测验证 → 写失败测试 → 修 → 测试转绿 → commit。P2 小修随同分支顺带。
1. P0-1（契约断裂，影响面最大）→ 2. P0-3（同为契约）→ 3. P0-2 + P2-10（同文件）→ 4. P0-4（文档）→ 5. P2-3 / P2-9（小修）

## M2 测试补盲

- **P1-5**：CI 加 Postgres service job，`VIEWER_TEST_PG_DSN` 指向它，跑 `go test ./...`（含 pgstore 测试）
- **W-0001**：`server/internal/api/design.go` 全部 11 条路由的 Go 测试（mock edit-service，断言 envelope 包装）——与 P0-1 修复同 PR 或紧随其后
- **W-0002**：ChatSidebar SSE 测试（web，MockEventSource）
- **W-0003**：flows 单测——`design_builder.py` SchemaError 分支、`dxf_from_design.py`（含 shaft fixture）；converter 测试加进 CI（当前 ci.yml 有 converter job，确认其在） 
- 目标比率（AGENTS.md 纪律）：新增实现代码的测试量 ≥ 3 倍

## M3 发布化（v0.1.0）

- **W-0004**：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置（env 文件），文档写进 site quickstart
- **W-0005**：仓库卫生——Issue/PR 模板、CONTRIBUTING 完善、示例模型入库
- **P2-7**：英文 Viewer 使用 6 页
- 许可证审计收尾（沿用原 open-source-plan 结论，下表）→ `git tag v0.1.0` + `gh release create`

### 许可证审计表（自 open-source-plan.md 迁入，2026-07-30 核对）

| 依赖 | 许可证 | 结论 |
|---|---|---|
| ifcopenshell / ifcdiff / ifcquery | LGPL-3.0 | 独立进程/PyPI 依赖使用，兼容 AGPL；已全部 PyPI 自包含（roadmap 已完成项），原「ifcdiff 本地 editable」问题已关闭 |
| deepdiff | MIT | 兼容 |
| pgx/v5 | MIT | 兼容 |
| xeokit-sdk / xeokit-convert | AGPL-3.0 | 同许可证，保持 AGPL 的现实理由 |
| web-ifc | MPL-2.0 | 兼容 |
| React / Vite / zustand / FastAPI / pydantic | MIT/BSD | 兼容 |

LICENSE 策略维持 AGPL-3.0-only + NOTICE 归档边界声明（现状已规范）。

## M4 结构加固 + 身份收编

- P1-2（put_entity 原子性）→ P1-3（状态持久化 + LRU）→ P1-4（chat.go 拆分）→ P1-1（token 中间件）
- P2-8（diff 去重）：抽 `summarize_changes()` 公共函数
- **P2-1 SCAD 遗产收编**（需用户裁决，三选一）：
  1. **保留归档**：pyproject/uv.lock/MANIFEST 改为 aiifc 身份或删除，`src/`、`skills/simplecadapi/` 加归档说明保留
  2. **移出仓库**：`src/`、`skills/simplecadapi/` 拆到独立 repo，主仓瘦身
  3. **彻底删除**：靠 git 历史留存
- 顺带：convert/queue.go 错误吞咽、edit.go metadata 静默降级、diffing.py 跳 GUID 的日志补齐

## 节奏建议

M1（1-2 天）→ M2 与 M3 可并行 → v0.1.0 发布 → M4 排入 v0.2。
