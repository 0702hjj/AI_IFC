AI BIM 工作流开发评估报告
一、项目整体格局
gaiass/
├── AI_IFC/          ← 从 SimpleCADAPI fork，目标是"AI 生成 IFC"
│   ├── src/simplecadapi/    ← 原 SCAD SDK（OCP-native，生成 STEP/STL）
│   ├── skills/simplecadapi/ ← 原 SCAD skill 包（17 条 MUST + 201 页 API 文档）
│   ├── research/            ← 调研非常充分（IFC/SCAD/web/MCP 四个方向）
│   ├── viewer/              ← IFC Web 显示（Go+Node+React+xeokit，已成型）
│   ├── docs/architecture/   ← viewer 路线图 + SCAD 架构评审
│   └── examples/            ← 全是 SCAD 的（01~20，无 IFC 示例）
├── IfcOpenShell/    ← v0.8.0 官方源码（事实标准，含 ifcmcp/ifcedit/ifcquery）
├── gaia_agent/      ← Go 后端 agent 平台（PostgreSQL，无 IFC 集成）
└── gaia_api/        ← Go API 服务（无 IFC 集成）
二、四条工作线现状评估
工作线 1：AI 生成 IFC 的 skill —— 【0% 完成，地基已备好；2026-07-30 起由另一同学负责，本仓库提供接入架构（roadmap.md §四）】
- research/ifc/ 调研极其扎实：ifcopenshell_python_dev_notes.md 是可直接当 skill 底稿的开发参考；simplecadapi_skill_anatomy.md 已给出精确的复刻清单（SKILL.md 骨架 + 按 IFC 领域分组的 api/README + 4 段式机器生成文档 + MODELING_WORKFLOWS 7 场景）；ifc_structrue_breakdown.md 提出了"骨架优先"建模策略（先纯语义树，再增量填几何/材质/属性）。
- AI_IFC/skills/ 下只有 simplecadapi，没有 ai_ifc。examples 里 20 个全是 SCAD 的，0 个 IFC 生成示例。
- IfcOpenShell 自带 ifcmcp（31 个工具，stdio）+ ifcedit（discover.py 可批量生成 API 文档），这套正是复刻 SCAD skill 的现成工具链，但目前 .mcp.json 只配了 postgres MCP，没启用 ifcmcp。
工作线 2：viewer —— 【~95% 完成，已是 BIM Review Platform】（2026-07-29 更新，迭代 N+1 已落地）
已完成（TDD 全程，server 56 测试 / web 84 测试 / smoke 端到端含 Issue + override/changes 链路）：
- converter：IFC→XKT+metadata.json，web-ifc 提取空间树+pset，id 一致性校验
- server：Go stdlib + pgx/v5（唯一第三方依赖），上传/转换队列/列表/下载/删除/重试，路径穿越防护，重启恢复；Issue REST API（CRUD+截图）；属性 override（白名单字段 PUT）+ 修改记录 change log API；Issue/override/changes 三类存储均为 File/Pg 双实现（`pgDSN`/`VIEWER_PG_DSN` 启用 PG）
- web：模型库页、xeokit 加载+拾取高亮、自建模型树（搜索/类型过滤/显隐）、PropertyPanel（搜索/折叠/复制 + 白名单字段编辑、override 覆盖显示带修改标记）、可见性工具栏（Hide/Isolate/X-Ray）、IssuePanel（Issues/修改历史双 tab）、IssuePins 3D HTML 钉（点击定位）、剖切、测量、NavCube
对照 docs/architecture/viewer.md 的路线图（已更新为迭代计划）：
| 优先级 | 组件 | 现状 |
| P0 | Property Inspector | ✅ 有（只读展示 + 搜索/折叠/复制；编辑能力见属性修改器行） |
| P0 | Model Tree + 过滤 | ✅ 有（搜索 + 分类过滤 + hide） |
| P0 | Issue/Markup | ✅ 有（创建/列表/状态流转/相机恢复/截图；文件/PG 双存储） |
| P1 | 测量 | ✅ 距离有 |
| P1 | Hide/Isolate/X-Ray 工具栏 | ✅ 有 |
| P1 | 版本对比 Diff Viewer | ❌ 没做（迭代 N+2，IfcDiff Python 服务） |
| P2 | 属性修改器 | ✅ override 阶段已落地（白名单字段编辑 + change log；真改 IFC 迭代 N+2） |
| 收尾 | 3D Issue Pin + 真机截图验证 | ✅ 已落地（钉点击定位 + 真机浏览器验证通过） |
工作线 3：后端 DB 集成 —— 【viewer 侧已落地，平台侧未对接】
- viewer 模型文件仍为文件系统（uploads/{id}.ifc + models/{id}/），但 Issue/修改记录/属性 override 已可平移 PostgreSQL（File/Pg 双实现，pgDSN 切换，启动自动建表 issues/changes/overrides）。
- gaia_agent/gaia_api 用 PostgreSQL（见 .mcp.json），但 viewer 完全独立、未对接。research/scad/techmap.md 已设计好后端分层（Intent Isolation + RAG + Tool Layer），但未落地。
工作线 4：工作流与 IfcOpenShell 的符合度 —— 【偏离】
- viewer 用的是 web-ifc（That Open 公司）+ xeokit-convert，不是 IfcOpenShell。研究文档 frontend_load.md 自己也说"IfcOpenShell WASM 启动重，不适合生产级前端"，所以选了 web-ifc——但这导致前后端不是同一套 API（techmap.md 明确要求"同一套 ifcopenshell.api"）。
- IFC 生成侧目前只有 SCAD（出 STEP），没有一条 ifcopenshell 的生成代码。
三、核心矛盾与风险
1. 研究层与实现层断裂：research/ifc 下结论清晰（用 IfcOpenShell api、复刻 SCAD skill、骨架优先），但 src/ skills/ examples/ 三处都还是 SCAD 原样，没有任何 IFC 生成代码。SCAD 的 SDK 代码（src/simplecadapi/）对 IFC 几乎无用——IFC 不是几何问题而是语义+空间结构+关系问题，SCAD 的 GraphSession/QL/topology 那套不能照搬。
2. viewer 技术路线与 IfcOpenShell 割裂【已决策，2026-07-29】：viewer 走 web-ifc+xeokit（前端展示不变）；「真改 IFC」与 Diff Viewer 统一由后端引入 IfcOpenShell Python 服务承载（对齐 deep-research-report §2.2/§1.3），属性修改走「先 override 后真改」两阶段，前端 WASM 方案排除。
3. DB 缺位【已落地 PG】：Issue/属性 override/修改记录已平移 PostgreSQL（PgStore，pgx/v5，配置 `pgDSN`/`VIEWER_PG_DSN` 启用，默认仍文件存储），修改记录对齐报告 §1.1 commit 模型（author/timestamp/old→new/provenance）。RAG（pgvector）仍未起步。
4. ifcmcp 未启用是低垂果实【已移交】：官方 ifcmcp 已经提供 31 个工具（含 ifc_plot/ifc_render 视觉反馈、ifc_list/ifc_docs/ifc_edit 发现式编辑）——AI 生成线（另一同学）可直接启用；本仓库侧重把 Python 编辑服务做成人/AI 同一套 API（MCP 化 v1.1 候选）。
四、下一步迭代计划（2026-07-30 更新，总计划见 docs/architecture/roadmap.md，目标映射见 research/overview.md）
方向决策：快速上线并开源 v1（自托管 docker compose、审查+编辑为主、SCAD 遗产归档）；AI 生成由另一同学负责，我们交付可接入架构。
迭代 N+1（✅ 已完成，2026-07-29，commits 8f41770 起）：
1	Issue 接 PG + 修改记录/历史	✅ PgStore 平移（File/Pg 双实现）；change log 对齐 deep-research-report §1.1 commit 模型
2	属性修改器（override 阶段）	✅ 完成「看→发现→定位→修改→跟踪」人的闭环第一步；白名单字段 + override + change log，不改 IFC 本体
3	3D Issue Pin + 真机截图验证	✅ Pin 落地（点击定位）；真机浏览器验证通过（截图非空白、钉居中、属性编辑入历史）
迭代 N+2（下一迭代，引入 IfcOpenShell Python 编辑服务，详见 roadmap.md §二）：
4	Python 服务骨架 + 实体编辑 API	FastAPI + ifcopenshell；报告 §2.2 PUT entities/{guid} + pending/commit（§2.4 Figure 2）
5	IfcDiff 集成 + Diff Viewer	报告 §1.3 按 GlobalId 语义 diff，绿/红/黄着色 + 属性 diff
6	override 迁移真改 + change log 升级	override 回放为真实 IFC 修改；change log 补 operation/diff 字段（§1.1 完整 schema）
7	AI 接入口	双角色同一编辑 API（§2.1）+ 工具 schema 文档（§2.3 REST 形态）+ docs/ai-integration.md
迭代 N+3（上线/开源就绪，详见 roadmap.md §三）：
8	部署化	docker compose 一键起（server/web/PG/Python 服务/converter），配置外置
9	文档与开源工程化	README 重写（en 主）、SCAD 归档说明、AI 接入指南、CI（GitHub Actions）、LICENSE 审计、v0.1.0 发布
AI 生成线（另一同学负责，我们已备调研与接入口）：
-	ifcmcp + ai_ifc skill + IFC 生成 examples（骨架优先）	调研已 90% 到位（research/ifc/）；接入走我们的双角色编辑 API，MCP 化 v1.1 候选
一句话总结：viewer 已从"纯展示"变为"审查平台"（迭代 N+1 完成：Issue/修改记录平移 PG、属性 override 修改器、3D Issue Pin），下一步按 roadmap.md 推进——N+2 引入 IfcOpenShell Python 服务做真改 IFC 与 Diff 并预留 AI 接入口，N+3 完成部署/文档/CI 后开源 v1；AI 生成由另一同学并行推进。
