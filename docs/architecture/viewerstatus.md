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
工作线 1：AI 生成 IFC 的 skill —— 【0% 完成，地基已备好】
- research/ifc/ 调研极其扎实：ifcopenshell_python_dev_notes.md 是可直接当 skill 底稿的开发参考；simplecadapi_skill_anatomy.md 已给出精确的复刻清单（SKILL.md 骨架 + 按 IFC 领域分组的 api/README + 4 段式机器生成文档 + MODELING_WORKFLOWS 7 场景）；ifc_structrue_breakdown.md 提出了"骨架优先"建模策略（先纯语义树，再增量填几何/材质/属性）。
- AI_IFC/skills/ 下只有 simplecadapi，没有 ai_ifc。examples 里 20 个全是 SCAD 的，0 个 IFC 生成示例。
- IfcOpenShell 自带 ifcmcp（31 个工具，stdio）+ ifcedit（discover.py 可批量生成 API 文档），这套正是复刻 SCAD skill 的现成工具链，但目前 .mcp.json 只配了 postgres MCP，没启用 ifcmcp。
工作线 2：viewer —— 【~90% 完成，已是 BIM Review Platform】（2026-07-29 更新）
已完成（TDD 全程，server 24 测试 / web 47 测试 / smoke 端到端含 Issue 链路）：
- converter：IFC→XKT+metadata.json，web-ifc 提取空间树+pset，id 一致性校验
- server：Go stdlib，上传/转换队列/列表/下载/删除/重试，路径穿越防护，重启恢复；Issue REST API（CRUD+截图，文件存储，Store 接口预留 PG）
- web：模型库页、xeokit 加载+拾取高亮、自建模型树（搜索/类型过滤/显隐）、PropertyPanel（搜索/折叠/复制）、可见性工具栏（Hide/Isolate/X-Ray）、IssuePanel（创建带相机+截图/状态流转/视角恢复）、剖切、测量、NavCube
对照 docs/architecture/viewer.md 的路线图（已更新为迭代计划）：
| 优先级 | 组件 | 现状 |
| P0 | Property Inspector | ✅ 有（只读，含搜索/折叠/复制；修改功能列入迭代 N+1） |
| P0 | Model Tree + 过滤 | ✅ 有（搜索 + 分类过滤 + hide） |
| P0 | Issue/Markup | ✅ 有（创建/列表/状态流转/相机恢复/截图；文件存储，PG 平移列入迭代 N+1） |
| P1 | 测量 | ✅ 距离有 |
| P1 | Hide/Isolate/X-Ray 工具栏 | ✅ 有 |
| P1 | 版本对比 Diff Viewer | ❌ 没做（迭代 N+2，IfcDiff Python 服务） |
| P2 | 属性修改器 | ❌ 只读（迭代 N+1，先 override 后真改两阶段） |
| 收尾 | 3D Issue Pin + 真机截图验证 | ❌ 没做（迭代 N+1） |
工作线 3：后端 DB 集成 —— 【0% 完成，已决策平移路径】
- viewer 的 store.go 是纯文件系统（uploads/{id}.ifc + models/{id}/model.json），明确 design.md 写"无DB"。
- gaia_agent/gaia_api 用 PostgreSQL（见 .mcp.json），但 viewer 完全独立、未对接。research/scad/techmap.md 已设计好后端分层（Intent Isolation + RAG + Tool Layer），但未落地。
工作线 4：工作流与 IfcOpenShell 的符合度 —— 【偏离】
- viewer 用的是 web-ifc（That Open 公司）+ xeokit-convert，不是 IfcOpenShell。研究文档 frontend_load.md 自己也说"IfcOpenShell WASM 启动重，不适合生产级前端"，所以选了 web-ifc——但这导致前后端不是同一套 API（techmap.md 明确要求"同一套 ifcopenshell.api"）。
- IFC 生成侧目前只有 SCAD（出 STEP），没有一条 ifcopenshell 的生成代码。
三、核心矛盾与风险
1. 研究层与实现层断裂：research/ifc 下结论清晰（用 IfcOpenShell api、复刻 SCAD skill、骨架优先），但 src/ skills/ examples/ 三处都还是 SCAD 原样，没有任何 IFC 生成代码。SCAD 的 SDK 代码（src/simplecadapi/）对 IFC 几乎无用——IFC 不是几何问题而是语义+空间结构+关系问题，SCAD 的 GraphSession/QL/topology 那套不能照搬。
2. viewer 技术路线与 IfcOpenShell 割裂【已决策，2026-07-29】：viewer 走 web-ifc+xeokit（前端展示不变）；「真改 IFC」与 Diff Viewer 统一由后端引入 IfcOpenShell Python 服务承载（对齐 deep-research-report §2.2/§1.3），属性修改走「先 override 后真改」两阶段，前端 WASM 方案排除。
3. DB 缺位阻塞协同【部分缓解】：Issue 已可文件持久化；迭代 N+1 用 PgStore 平移到 PostgreSQL（接口已预留），修改记录/历史对齐报告 §1 commit 模型。RAG（pgvector）仍未起步。
4. ifcmcp 未启用是低垂果实：官方 ifcmcp 已经提供 31 个工具（含 ifc_plot/ifc_render 视觉反馈、ifc_list/ifc_docs/ifc_edit 发现式编辑），把它接进 .mcp.json 立刻就能让 LLM 操作 IFC，是验证 AI 工作流最快路径。
四、下一步迭代计划（2026-07-29 更新，详见 docs/architecture/viewer.md）
按「最终可用性」排序，viewer 线优先于 AI 线：
迭代 N+1（纯现有技术栈）：
1	Issue 接 PG + 修改记录/历史	PgStore 平移（接口已预留）；change log 对齐 deep-research-report §1.1 commit 模型，为属性修改奠基
2	属性修改器（override 阶段）	完成「看→发现→定位→修改→跟踪」人的闭环第一步；对齐报告 §2.4 交互流，不改 IFC 本体
3	3D Issue Pin + 真机截图验证	审查协同收尾
迭代 N+2（引入 Python 服务）：
4	Diff Viewer	IfcDiff 按 GlobalId 语义 diff（报告 §1.3），绿/红/黄着色 + 属性 diff
5	真改 IFC	同一 Python 服务承载报告 §2.2 PUT entities/{guid} + pending/commit，override 平滑迁移
AI 线（并行候选，优先级低于 viewer 线）：
6	启用 ifcmcp + 写最小 ai_ifc skill	调研已 90% 到位；ifcmcp 现成，最快验证 AI 操作 IFC
7	补 IFC 生成 examples（骨架优先最小样例）	ifc_structrue_breakdown.md 已给验收标准
8	RAG 冷启动（IFC4 schema 入 pgvector）	可延后
一句话总结：viewer 已从"纯展示"变为"审查平台"（P0 全部落地），下一迭代主攻"人的修改闭环"——先把 Issue/修改记录平移到 PG、做属性 override 修改，再引入 IfcOpenShell Python 服务做 Diff 与真改 IFC；AI 生成 IFC 主线（ifcmcp + ai_ifc skill + examples）作为并行候选随后跟进。
