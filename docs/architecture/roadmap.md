# 开源 v1 总迭代路线图（2026-07-30）

> 本文是跨工作线的总计划；viewer 线细节见 [viewer.md](./viewer.md)，现状评估见 [viewerstatus.md](./viewerstatus.md)，
> 与 deep-research-report 的目标映射见 `research/overview.md`。

## 〇、目标与范围决策（2026-07-30 确认）

**目标：快速上线并开源第一版（v1）自托管 BIM 审查/编辑服务。**

| 决策点 | 结论 |
| --- | --- |
| v1 能力范围 | **审查 + 编辑为主**：viewer 审查平台（已完成）+ 真改 IFC + Diff Viewer（迭代 N+2）；AI 生成不进 v1 功能面 |
| 上线形态 | **自托管开源**：docker compose 一键起（server + web + PG + Python 服务 + converter），单机无认证，文档写明适用内网/个人 |
| AI 生成 | **由另一同学负责**；我们交付「可接入的架构」：双角色编辑 API、commit/provenance 模型、工具 schema 文档、MCP 化预留 |
| SCAD 遗产 | **保留归档**：`src/simplecadapi` + SCAD examples + `skills/simplecadapi` 保留并加归档说明，README 聚焦 IFC |
| 对齐文档 | `md/dxf_agent/deep-research-report.md`（目标映射与实现情况：`research/overview.md`） |

**Out of scope（v1 不做）**：鉴权/多用户、AI 生成本体、IFC→Python 管线（报告 §3，后续版本）、Git 存 IFC（报告 §4 混合存储的 Git 半，暂缓）、RAG（pgvector）。

## 一、现状基线（2026-07-30）

- viewer 线 **~95%**：BIM Review Platform 成型；迭代 N+1 完成（Issue/change log/override 三 store File/PG 双实现、属性修改器 override 阶段、3D Issue Pin、真机验证通过）。详见 viewerstatus.md
- 报告 §2.4 修改流已在 override 阶段落地（选中 → 改值 → 保存 → 记录 → 历史）；§1.1 commit 模型已落地 author/timestamp/provenance 半
- DB 缺位已解决：PG（独立库 `ai_ifc_viewer`，自动建表 issues/changes/overrides），`pgDSN` 切换，FileStore 零依赖可跑
- 未起步：IfcOpenShell Python 服务（真改 IFC、IfcDiff）、部署化、开源工程化

## 二、迭代 N+2：IfcOpenShell Python 编辑服务（真改 IFC + Diff）

目标：引入 IfcOpenShell Python 服务，完成「真改 IFC」与「版本对比」，并把编辑 API 设计成**人/AI 双角色同一套**（报告 §2.1），为另一同学的 AI 生成线留好接入口。

架构形态：

```
浏览器(web) ──► Go server ──► Python 编辑服务 (FastAPI + ifcopenshell)
                 │  编排/代理        ├─ PUT /models/{id}/entities/{guid}（pending → commit）
                 │                  ├─ POST /models/{id}/diff（IfcDiff，GlobalId 语义）
                 │                  └─ 改后落盘 IFC → 触发重转 XKT
                 ├─ PG (issues/changes/overrides + commit diff)
                 └─ Node converter（沿用，XKT 重转）
AI agent（另一同学）──► 同一套编辑 API（REST 直连或经 Go 代理，provenance.source="AI"）
```

任务分解（可转 SDD plan 执行）：

1. **Python 服务骨架**：FastAPI + ifcopenshell（`viewer/edit-service/` 或独立顶层目录）；`/health`、模型加载/保存、文件锁（单模型串行写）；uv 管理依赖
2. **实体编辑 API**：`PUT /models/{id}/entities/{guid}` 真改 IFC 属性（报告 §2.2）；pending → commit 两阶段（报告 §2.4 Figure 2：改先进 pending，commit 才落盘 + 写历史）；`GET /models/{id}/history`
3. **IfcDiff 集成**：`POST /models/{id}/diff`（base/target 两版本 → added/removed/changed，GlobalId 语义，报告 §1.3）
4. **Go server 编排**：编辑请求代理至 Python 服务；commit 后触发 converter 重转 XKT（沿用现有队列）；**override → 真改迁移**（把 PG overrides 逐条回放为真实 IFC 修改，迁移后清空 override 并写 change log）
5. **change log 升级**：补 `operation` 与 `diff` 字段（对齐报告 §1.1 完整 schema）；provenance 枚举校验（UI/AI）
6. **web Diff Viewer**：V1/V2 版本选择 → 绿(新增)/红(删除)/黄(修改)着色 + 属性 diff 列表（old→new）；真改后 viewer 自动刷新
7. **AI 接入口**：编辑 API 的 OpenAPI/工具 schema 文档（报告 §2.3「tool catalog」的 REST 形态）；`docs/ai-integration.md` 初版

## 三、迭代 N+3：上线 / 开源就绪

1. **部署化**：docker compose 一键起（Go server、web 静态托管、PG、Python 编辑服务、Node converter）；配置外置（`.env.example`，DSN/端口/数据卷）；数据目录卷映射
2. **文档**：根 README 重写（英文为主、中文为辅：定位/截图/快速开始/架构图）；SCAD 遗产归档说明（README 一节 + `src/simplecadapi/README` 标注 archived）；`docs/ai-integration.md` 完善（双角色接入、provenance、commit 模型、MCP 化路线）
3. **开源工程化**：GitHub Actions CI（go test、web test、PG service 集成、smoke）；LICENSE 审计（AGPL-3.0 与全部依赖兼容性，含 pgx/xeokit/ifcopenshell）；issue/PR 模板；`.gitignore` 复查 + 密钥扫描
4. **发布**：v0.1.0 tag + release notes + 示例模型（可用 research 样例 IFC）

## 四、AI 接入口架构（交付给另一位同学）

AI 生成本体不在本仓库范围，但 v1 架构保证其可接入：

| 报告章节 | 接入口 | 状态 |
| --- | --- | --- |
| §2.1 双角色 | 人：viewer → Go → Python 服务；AI：REST 直连同一编辑 API | N+2 落地 |
| §1.1 commit 模型 | author/timestamp/provenance(UI\|AI) 已落地；operation/diff 字段 N+2 补齐 | 部分 ✅ |
| §2.3 工具目录 | 编辑 API 的 OpenAPI 工具 schema 文档（REST 形态，可直接喂给 LLM） | N+2 |
| MCP 化 | 报告 §4.1 建议 REST+MCP 双暴露；v1 先 REST，MCP 薄包装（参考 ifcmcp 31 工具模式）列为 v1.1 候选 | 预留 |
| §2.3 沙箱/代码执行 | 属 AI 侧范围；架构上不阻塞（Python 服务进程隔离，后续可加 execute 端点） | 预留 |

## 五、里程碑排序与验收

| 序 | 迭代 | 内容 | 验收 |
| --- | --- | --- | --- |
| 1 | N+2 | Python 编辑服务 + 真改 IFC + Diff Viewer + override 迁移 | 浏览器改属性 → IFC 真改 → 重转刷新 → diff 可查；AI 可用 REST 完成同样操作；双模式（File/PG）测试全绿 + 真机验证 |
| 2 | N+3 | 部署 + 文档 + CI + 发布 | 干净机器 `docker compose up` 一键可用；README 快速开始可复现；CI 绿；v0.1.0 发布 |

关键路径：Python 服务骨架 → 编辑 API → IfcDiff → override 迁移 → Diff UI；N+3 的部署/文档可在 N+2 后段并行启动。

## 六、风险与对策

- **IfcDiff 大模型性能**：数百 MB IFC diff 可能慢 → 先限定属性级 diff 场景，几何 diff 按需；必要时 HDF5/流式（报告 §4.4）
- **真改后重转时延**：converter 全量重转数秒 → v1 接受（pending/commit 模型下用户有预期）；后续考虑增量
- **override → 真改迁移冲突**：迁移时 IFC 原值可能已被外部改动 → 迁移写 change log 带 oldValue（真原值），失败条目保留 override 并提示
- **AGPL 传染性**：开源前做依赖许可证审计（N+3 任务 3），必要时调整依赖或联系改许可证
- **多客户端并发写**：v1 单机单用户假设，Python 服务文件锁串行化即可；多用户属 v2
