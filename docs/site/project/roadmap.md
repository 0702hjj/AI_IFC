# Roadmap

> 公开版只保留已完成、近期与后续；内部迭代细节见仓库 `docs/internal/`。

## 已完成

- 审查平台：上传/转换、模型树、属性检查、可见性工具、剖切、测量、Issue + 3D Pin、属性 override 与修改历史；issues/overrides/change log 的 File / PostgreSQL 双实现。
- 真改 IFC：edit-service（pending → commit）、版本快照、属性级语义 diff、Diff Viewer、override → 真改迁移。
- AI 接入口：人/AI 双角色编辑 API（provenance 区分）、OpenAPI 工具目录、接入指南。
- 文档站：本 VitePress 站点、PR 构建校验与 GitHub Pages 自动部署。

## 近期

- 部署化：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置。
- 开源工程化：依赖许可证审计收尾（含 ifcdiff 自包含处理）、示例模型、`v0.1.0` 发布。
- 仓库卫生：Issue/PR 模板、贡献指南完善。

## 后续

- **双语扩展**：中文文档稳定后增加英文 locale；英文优先覆盖首页、快速开始、总体架构、贡献与 API 入口；禁止仅创建空的英文导航或占位页。
- **API 自动生成**：从 edit-service 的 FastAPI OpenAPI schema 生成或同步 API 页面；为 Go server 建立机器可读契约；CI 检测 schema 与已提交产物漂移；人工指南继续解释工作流与语义。
- 编辑 API 的 MCP 封装；几何 diff；增量重转；diff 超时控制。

## v1 范围外

多用户/鉴权、AI 生成 IFC 本体（并行线经编辑 API 接入）、IFC → Python 生成管线、RAG、Git 存 IFC、文档版本切换。
