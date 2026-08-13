# 贡献指南

欢迎贡献！本文件只做入口索引，规则以各单一事实来源为准，不重复复制。

## 命令与契约

组件测试/启动命令、测试纪律（TDD、测试量 ≥ 实现 3 倍、异步写盘等待）、API 契约（envelope、check:api）、Git 工作流与 commit 规范，一律见 [AGENTS.md](AGENTS.md)。

## 贡献流程

开发环境、本地验证、文档贡献与 License 说明见文档站贡献页：
https://0702hjj.github.io/AI_IFC/project/contributing
（源文件：[`docs/site/project/contributing.md`](docs/site/project/contributing.md)）

## 工作项

仓库以 `docs/work/items/` 管理工作项：认领 → 置 `in-progress` → 按验收标准执行 → 置 `done`。流程详见 [docs/work/README.md](docs/work/README.md)。

## 提 Issue / PR

- Issue：使用仓库提供的 Bug 报告 / 功能建议模板（`.github/ISSUE_TEMPLATE/`）。
- PR：目标 `main`（受保护，禁止直推），填写 PR 模板勾选清单，CI 绿后合并。

## License

本仓库为 Apache-2.0，贡献即表示同意以该许可证发布。
