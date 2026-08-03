# Roadmap

> 公开版只保留已完成、近期与后续；内部迭代细节见仓库 `docs/internal/`。

## 已完成

- 审查平台：上传/转换、模型树、属性检查、可见性工具、剖切、测量、Issue + 3D Pin、属性 override 与修改历史；issues/overrides/change log 的 File / PostgreSQL 双实现。
- 真改 IFC：edit-service（pending → commit）、版本快照、属性级语义 diff、Diff Viewer、override → 真改迁移。
- AI 接入口：人/AI 双角色编辑 API（provenance 区分）、OpenAPI 工具目录、接入指南。
- 文档站：本 VitePress 站点、PR 构建校验与 GitHub Pages 自动部署。
- 文档增强：英文 locale（首页、快速开始、总体架构、贡献、API 入口）、edit-service API 参考页与 Go 端点清单的机器生成 + CI 漂移检测。

## 近期

- 部署化：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置。
- 开源工程化：依赖许可证审计收尾（含 ifcdiff 自包含处理）、示例模型、`v0.1.0` 发布。
- 仓库卫生：Issue/PR 模板、贡献指南完善。

## 后续

- **双语扩展（后续）**：其余页面（Viewer 使用、开发指南细节、项目组）的英文版本。
- **API 自动生成（后续）**：edit-service 的"代码 vs schema"漂移检测（需 ifcdiff 依赖自包含）；Go server 请求/响应 schema 的完整自动生成。
- 编辑 API 的 MCP 封装；几何 diff；增量重转；diff 超时控制。

## v1 范围外

多用户/鉴权、AI 生成 IFC 本体（并行线经编辑 API 接入）、IFC → Python 生成管线、RAG、Git 存 IFC、文档版本切换。
