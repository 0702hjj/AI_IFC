# 已知限制

以下限制是当前实现的真实边界，除特别说明外均属未交付能力而非缺陷：

## 部署与依赖

- **Docker Compose 未完成**：当前只有本地四进程部署方式（见 [环境要求与本地部署](/guide/quickstart)），不支持一键部署。
- **ifcdiff 为本地 editable 依赖**：edit-service 依赖仓库同级目录的 IfcOpenShell 源码 checkout；自包含处理（vendor 或 git source）在 [Roadmap](/project/roadmap) 中。
- **模型文件始终文件系统**：PostgreSQL 仅承载 issues / overrides / change log；uploads、XKT、元数据、版本快照仍在文件系统。
- **Python 侧存储仅文件模式**：PG 模式下 edit-service 的 history 与版本快照仍在文件。

## 编辑与并发

- **单机单用户、无认证**：provenance 是声明字段，无防伪语义；请勿将服务暴露到公网。
- **pending 只存内存**：edit-service 重启即丢失未 commit 的修改；history 与版本快照不受影响。
- **无多用户并发控制**：每模型一把锁串行化写，多用户/冲突合并属后续范围。
- **diff 无超时控制**：大模型可能阻塞。

## 功能边界

- **diff 仅属性级**：不提供几何 diff；entity 引用属性不参与比较。
- **AI 生成 IFC 本体未交付**：AI 通过同一套编辑 API 修改已有模型；生成能力属并行线。
- **MCP 封装未交付**：当前为 REST 形态。
- **OpenAPI 为仓库内静态文件**：自动生成与漂移检测属后续迭代。
- **仅中文文档**：英文 locale 为后续迭代。
