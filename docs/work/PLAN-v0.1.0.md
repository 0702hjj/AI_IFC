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
| v0.4 | 可复用性 + 上线健壮性 ✅（2026-08-11，分支 feat/v0.2-orchestrator-closure，PR #31）| 物理重组（viewer/ 拆分）+ Go OpenAPI + skill 打包器泛化 + services/ifc 独立调用文档 + diff 超时 + 重转去重 + stale 清扫 | 结构一步到位（services/ifc + web/server/converter/mcp 顶层化 + skills/aidxfv 收敛）；对外唯一入口机器可消费 OpenAPI；任意 skill 可打包；diff 超时 504；同源跳过重转 |
| v0.5 | 可移植复用 ✅（2026-08-12，spec: 2026-08-12-portability-reuse-design.md，分支 feat/v0.5-portability-reuse，PR #31）| W-0026..W-0029（W-0030/W-0031 已于 2026-08-20 关闭：前者立项目的已达成，后者 wontfix——Docker 部署形态已移除） | 对接契约入站；services/ifc 镜像冒烟通过；skill 版本化 + Release runbook 文档化（首发布随下迭代）；aibim-orchestrator 提示词包可打包、W-0017 关闭 |
| v0.6 | services/cad script-as-source chunk A ✅（2026-08-12，分支 feat/v0.5-portability-reuse 累积，PR #31）| W-0032, W-0033 | cad_script_lib 契约+XDATA 身份测试绿；services/cad 骨架端点与沙箱全测试绿 |
| v0.6 | services/cad script-as-source chunk B ✅（2026-08-13，分支 feat/v0.6-cad-diff，PR #34）| W-0034, W-0035 | diff 引擎与 locate/edit-call 测试绿 |
| v0.6 | services/cad script-as-source chunk C ✅（2026-08-13，分支 feat/v0.7-cad-render，PR #36）| W-0039, W-0040 | render.json 实体带 key + unsupported 明面化；Go kind 分流 + cad 端点代理（edit-call 除外）契约测试绿 |
| v0.6 | services/cad script-as-source chunk D ✅（2026-08-14，分支 feat/v0.8-dxf-viewer，PR #37）| W-0041 | kind=dxf 模型 ViewerPage 分流 Canvas 只读查看器（七类实体/pan-zoom/图层/选中属性/unsupported 明面化）测试绿；编辑 UI 另立 chunk 且开工需用户确认 |
| v0.6 | chunk E：Eino 替换 opencode + 主子编排 + web-ifc 查看器 ✅（2026-08-17 实现完毕，分支 feat/v0.9-eino-webifc，**整 chunk 单 PR** 收口）| W-0043, W-0044 | 进程内 Eino agent loop 替换 opencode（SSE/REST 契约逐字段不变）+ subagent 主子编排 + web-ifc/three IFC 查看器（与 xeokit 并存，默认 xeokit） |
| v0.10 | 中途预览 + DXF/webifc 编辑面 ✅（2026-08-18，PR #40）| W-0045 | run_script 成功推 viewer.staged SSE 事件 + 工具结果附 staging diff 摘要；dxf/webifc 自动刷新、xeokit 手动角标；dxf/webifc 分支挂 DesignPanel 全套编辑面 + dxf 选中定位脚本；aidxfv v1/v2 遗留删除 |
| v0.10.1 | 编辑面对齐收尾 ✅（2026-08-19，PR #43）| W-0046 | locate params_keys 断链修复（PARAMS 聚焦恢复）；webifc 选中面板补「定位脚本」；DesignPanel 版本列表加回滚按钮；script/run 响应附构件级 semanticDiff、run_script 摘要优先构件级计数；aiplan SKILL.md 补 version 修复打包 |
| v0.11 | 沙箱加固 + 移除 Docker 改宿主直跑 ✅（2026-08-19，PR #44）| W-0047 | bwrap 按需挂载堵跨租户读（不挂 /data//etc）；RLIMIT_FSIZE + stdout 泛洪截断 + 产物大小校验 + 并发闸（429）；rlimit 降级 fail-closed（ALLOW_RLIMIT_FALLBACK 开关）；部署形态实证后改为宿主直跑（移除 Docker，server 托管 web/dist）；部署文档强制 VIEWER_API_TOKEN |
| v0.12 | 文件行数门控合规重构 ✅（PR #48~#52，白名单收敛到 4 项）+ aiplan/aidxfv 审计收尾 | W-0049、W-0050 | 历史 plan 归档豁免 gate（白名单 25→19）；15 个超限文件按组件分 PR 拆分，纯重构不改行为、用例数不减；W-0050：golden meta 乱码键修复、假测试清理、依赖卫生、pack node 校验、删 aiplan 重复 source.dxf ×9 |
| v0.13 | agent 完整接入前端 + cad→ifc 消化管线（open，2026-08-21）| W-0051..W-0055 | W-0051：agent 前端流程对齐审查 + 交付执行代码加固（SSE 帧契约回归、三类对话全链、失败路径可观测）；W-0052：cad→ifc 消化管线重点完善 + 实验矩阵（≥6 形态全链保真度）；W-0053：cad 编辑两套依赖（dxfkit+archdxf）合并合适性评估（边界文档 + 打包一致性 + 方向决策）；W-0054：project 管理更新（项目详情/模型列表 REST、模型解绑联动、前端项目入口、kind 流转规则）；W-0055：GUI 调试 agent 快速工具收编（SSE 帧可视化 + 工具轨迹 + 确定性回放）|

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
