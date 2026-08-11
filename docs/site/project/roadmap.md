# Roadmap

> 公开版只保留已完成、近期与后续；可追踪的工作项与实施计划见仓库 `docs/work/`（审计 + milestone 计划）。

## 已完成

- 审查平台：上传/转换、模型树、属性检查、可见性工具、剖切、测量、Issue + 3D Pin、属性 override 与修改历史；issues/overrides/change log 的 File / PostgreSQL 双实现。
- 真改 IFC：edit-service（pending → commit）、版本快照、属性级语义 diff、Diff Viewer、override → 真改迁移。
- AI 接入口：设计师/AI 双角色编辑 API（provenance 区分）、OpenAPI 工具目录、接入指南。
- AI Skill（aiifc）：agent 无关的 IfcOpenShell 建模 skill（发现桩 + references + templates + workflows），含打包器与 CI 校验。
- Plan → DXF → IFC 工作流：可选的「辅助设计师」三阶段编排 skill，DXF 生成器（前端 svg 预览）。
- 确定性构件身份：稳定 `key` → `uuid5` 确定性 GlobalId → `Pset_AIIFC.designKey` 双向映射（脚本契约 #25-29 沿用）。
- API 统一版本化：对外契约 `/api/v1/{resource}/{id}`，Go server 唯一对外入口。
- 依赖自包含：`ifcopenshell` / `ifcdiff` / `ifcquery` 全部 PyPI 官方发布，无本地源码依赖。
- 测试整合：skill 打包测试收拢 `tests/skill/`，CI 覆盖 edit-service / skill-pack / flows 冒烟。
- Script-as-source（M5）：Python 构建脚本成为 IFC 唯一事实源——脚本契约（PARAMS + 确定性 GlobalId + build 入口）、脚本沙箱执行、WPS 式脚本暂存 + 大版本成对快照（scripts/v{n}.py + versions/v{n}.ifc）、脚本 diff（text + PARAMS 键级，大/小版本两级）、Design 面板 PARAMS 表单 + 脚本编辑器；design JSON 编辑管线直接下线（降级为 AI 起草辅助草稿，不进版本不参与 diff）。
- 文档站：本 VitePress 站点、PR 构建校验与 GitHub Pages 自动部署。
- 文档增强：英文 locale（首页、快速开始、总体架构、贡献、API 入口）、edit-service API 参考页与 Go 端点清单的机器生成 + CI 漂移检测。
- MCP server：编辑 API 的 MCP 薄封装（stdio，解析用户改后 IFC/DXF 并标 USER 来源）。
- 属性真改直通：属性编辑不再有 override 中间层，直接走 pending → commit 真改闭环。
- ChatSidebar 修复：AI 对话侧栏问题修复。
- Script-as-source 统一编辑（2026-08-08 迭代）：web 修改 = 改构建脚本——选中构件定位脚本调用点（ScriptMap，guid→designKey→行/列/origin）、PARAMS 表单 / libcst 标量改写（edit-call）+ 沙箱验证、上传 IFC 经 AI 复现为脚本（bootstrap.ifc 保留 + save 响应对齐计数）；L1 直改链路退役（410，回捞锚点 fb55a8a）；IFC 只物化最新大版本、历史按需重建（ifc_cache LRU 4）。
- 部署化：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置（`.env.example` 全默认值；CI compose-smoke 真冒烟）。
- 重转去重：IFC 未变（mtime 不新于 XKT）时跳过全量重转（不发 converting、不入队）；XKT 缺失 / 判断失败保守重转（宁可多转不可漏转）。（几何 diff 已随 script-as-source 覆盖：IFC 是脚本产物，diff 为脚本 diff + 属性级语义 diff。）

## 近期

- **平台框架（2026-08-11）**：两个对等逻辑（AI 生成 IFC / AI 生成 CAD）+ Agent 工作流推荐项入约；功能块横切结构（skill ×2 ↔ services ×2 ↔ 共享运行时）；物理重组一步到位（`viewer/` 拆分、`AI_CAD/skills/aidxfv*` 迁入 `skills/aidxfv/`，见 [框架 spec](https://github.com/0702hjj/AI_IFC/blob/main/docs/superpowers/specs/2026-08-11-platform-framework-design.md)）。
- **notify 事件化（2026-08-11）**：chat notify 按 Pure Core + Imperative Shell 重构，事件 URI 化（`aiifc://`），为 Agent 工作流控制打底。
- **services/cad（后续，可选项）**：CAD 段业务逻辑核心（diff + 面向前端修改的编辑 API，与 services/ifc 同构），配套 CAD skill 收敛入 `skills/aidxfv/`。
- 开源工程化：依赖许可证审计收尾、示例模型、`v0.1.0` 发布。
- 仓库卫生：Issue/PR 模板、贡献指南完善。

## 后续

- **双语扩展（后续）**：开发指南细节页（`development/` 除 `architecture`）、项目组（`known-limits`/`license`/`roadmap`）与 `reference/edit-api-reference` 的英文版本。
- **API 自动生成（后续）**：edit-service 的"代码 vs schema"漂移检测；Go server 请求/响应 schema 的完整自动生成。
- **前端参数化编辑增强**：edit-call 的 UI 化（属性面板内直接改标量参数，无需进脚本编辑器）；bootstrap 对齐报告的可视化。
- 计划 → 2D DXF → IFC 完整工作流。

## v1 范围外

多用户/鉴权、AI 生成 IFC 本体（已由 aiifc skill 覆盖生成、平台编辑 API 覆盖修改）、IFC → Python 生成管线、RAG、Git 存 IFC、文档版本切换。
