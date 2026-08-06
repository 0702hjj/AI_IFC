# 贡献指南

## 开发环境

见 [环境要求与本地部署](/guide/quickstart)。开发采用 TDD：先写失败测试再实现，测试文件与源码同目录。

## 本地验证

```bash
# 后端
cd viewer/server && go test ./... && go vet ./...
# 编辑服务
cd viewer/edit-service && uv run --group dev pytest
# 前端
cd viewer/web && npm test && npm run build
# 转换器
cd viewer/converter && npm test
# 文档
cd docs && npm ci && npm run docs:build
```

## 文档贡献

- 公开文档站源在 `docs/site/`，唯一信息源；修改后必须 `cd docs && npm run docs:build` 通过（死链会导致构建失败）。
- `docs/internal/` 不进入站点，仅作内部记录（原 `docs/archive/` 已随 2026-08-05 清理移除，见 git 历史）。
- 页面涉及未交付能力时，必须标注为 Roadmap，不得提供不可执行步骤。
- 移动或归档文档后，全仓 Markdown 相对链接必须同步更新。

## Commit 与 PR

- Commit 消息遵循仓库惯例：`feat:` / `fix:` / `docs:` / `ci:` / `chore:` 前缀 + 中文简短描述。
- PR 到 `main`：GitHub Actions 会运行现有 viewer CI 与文档构建；两者都必须通过。
- 不提交个人本机路径、密钥、运行时数据（`viewer/data/`）。

## License

本仓库为 AGPL-3.0-only。贡献即表示同意以该许可证发布；第三方组件归属见 [License 与第三方组件](/project/license)。
