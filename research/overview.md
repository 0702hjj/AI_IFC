# deep-research-report 目标 ↔ 实现情况总览

> 日期：2026-07-30（迭代 N+2 已落地；每次迭代后同步本文件）
> 报告：`~/Documents/md/dxf_agent/deep-research-report.md`（IfcOpenShell 版本控制 / 编辑 API / IFC→Python 管线）
> 总迭代计划：`docs/internal/architecture/roadmap.md`；现状评估：`docs/internal/architecture/viewerstatus.md`；当前版总体架构：`docs/internal/architecture/ai-bim.md`

## 分工声明

- **本仓库（AI_IFC）负责**：报告的「IFC 显示 + 人的修改 + 版本追踪/存储 + 供 AI 接入的编辑架构」
- **AI 生成本体（含 §2.3 AI 沙箱、§3 IFC→Python 工具）由另一同学负责**；我们交付可接入的架构（双角色编辑 API、commit/provenance 模型、工具 schema 文档、MCP 化预留）

## 目标映射表

| 报告章节 | 目标 | 状态 | 实现 / 计划位置 |
| --- | --- | --- | --- |
| §1.1 commit 模型（author/timestamp/operation/diff/provenance） | 每次变更记录完整 commit 元数据 | **✅** | 全部字段落地：`viewer/server/internal/change`（operation ∈ update/migrate、diff jsonb、provenance 枚举校验）；edit-service `edit-history.json` 另存真原值 oldValue |
| §1.2 存储选型 | Git/边车/DB 三路线比较 | **✅ 已决策** | DB 路线先行：PG 三表（issues/changes/overrides，File/PG 双实现可切换）；Git 存 IFC 暂缓；决策记录：`docs/internal/architecture/viewerstatus.md` 核心矛盾 2/3 |
| §1.3 IfcDiff（GlobalId 语义 diff） | added/removed/changed 结构化 diff | **✅** | `viewer/edit-service`（`app/diffing.py` + `app/versions.py`）：commit 版本快照、`POST /models/{id}/diff`，属性级（几何 diff 暂缓）；Diff Viewer 着色消费 |
| §1.4 provenance schema（PG Commits 表） | commit log 结构化存储 + 审计 | **✅ 简化版** | `changes` 表（列式 + provenance jsonb）；author 当前写死 local-user（单机无认证） |
| §2.1 双角色（人 / AI agent） | 同一 API 服务人与 AI | **✅ 架构预留** | provenance.source 枚举 UI/AI；AI 经 REST 直连同一编辑 API（N+2 随 Python 服务落地）；认证/RBAC 不做（单机自托管定位） |
| §2.2 实体编辑 API（`PUT /models/{id}/entities/{guid}`） | 改实体属性 | **✅ 真改已落地** | override 版：`PUT /api/models/{id}/entities/{entityId}/properties`（保留）；真改：`viewer/edit-service` `PUT /models/{id}/entities/{guid}`（fields/psets + pending/commit），Go 代理 `/api/models/{id}/edit/...`；override 可经 `POST /api/models/{id}/overrides/migrate` 迁移为真改 |
| §2.3 AI 工具目录 / 沙箱 | 工具 schema 供 LLM 调用；代码沙箱 | **✅ 接入口已交付 / 沙箱 👥** | 已交付：`docs/internal/ai-integration.md` + `docs/site/public/ai-tools.openapi.json`（FastAPI 导出，`scripts/export_openapi.py` 再生成）；MCP 薄包装列 v1.1 候选；沙箱属 AI 侧，架构不阻塞 |
| §2.4 前端修改流（选中→改参→API→commit→刷新） | 人的修改闭环 UX | **✅ 真改版已落地** | override 流（PropertyPanel）保留；真改流：PUT → pending → commit → XKT 重转 → ViewerPage 轮询自动重载；真机浏览器验证通过 |
| §2.5 React/xeokit 集成 | 3D 展示 + 参数控件 | **✅** | xeokit 自建封装（非 xeokit-react）：`viewer/web/src/viewer/`（ViewerContext/PropertyPanel/IssuePanel/IssuePins） |
| §3 IFC→Python 转换 | IFC 模型 → 可重放 Python 脚本 | **👥 / 后续版本** | 不进 v1；由 AI 生成线或 v2 跟进 |
| §4.1 设计选项结论 | 混合存储 / 语义合并 / REST+MCP / 沙箱 | **✅ 已按推荐决策** | 混合存储 DB 半已落地（Git 半暂缓）；语义 diff（GlobalId）N+2；REST 先行、MCP v1.1；AI 沙箱归另一同学 |
| §4.2 推荐架构（FastAPI + Git + DB + React/xeokit + MCP） | 总体技术形态 | **🚧 演进中** | React/xeokit ✅；DB ✅；FastAPI Python 服务 ✅（N+2）；Git 仓暂缓；MCP v1.1 |
| §4.3 实施 roadmap（6 阶段） | 24 周里程碑 | **节奏不同（自建路线）** | 我们先落地 viewer（报告未含），再按 §2.2/§1.3 反推 N+2；§4.3 Phase 2（版本控制原型）≈ 我们 N+2，Phase 4（AI 集成）≈ 另一同学 + 我们接入口 |

## 关键偏差说明

1. **前端解析栈**：报告未指定前端 IFC 解析方案；我们选 web-ifc + xeokit-convert（非 IfcOpenShell WASM），理由与决策记录见 `docs/internal/architecture/viewerstatus.md` 核心矛盾 2 —— 前端展示不变，「真改 IFC」统一由后端 IfcOpenShell Python 服务承载
2. **oldValue 语义**【已解决，N+2】：真改流的 oldValue 由 edit-service 从 IFC 读取真原值（pending/commit history + commit 编排写 change log）；override 迁移同样带真原值。override 阶段旧记录（前次 override 值）保留为历史数据，不回溯
3. **认证/RBAC**：报告 §2.1 的 OAuth2/JWT/RBAC 不落地 —— v1 定位单机自托管无认证，公网/多用户属 v2

## 状态图例

✅ 已落地（附证据位置）｜🚧 已排期（注明迭代）｜👥 另一同学负责（我们提供接入口）｜暂缓/不做（注明原因）
