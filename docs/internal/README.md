# 内部文档与内部 Wiki

`docs/internal/` 存放不进入公开文档站的内部资料（团队同步、源文档、架构评估、内部计划）。公开文档站源在 `docs/site/`，两者边界见 `docs/superpowers/specs/2026-08-02-documentation-site-design.md` §5。

## 内部 Wiki（本地/私有访问）

把公开站点、内部文档与迭代计划组装成**一个可浏览的 wiki**（含导航与搜索），**不部署到公开 GitHub Pages**：

```bash
cd docs
npm ci
npm run docs:dev:internal     # 组装 + 本地预览（默认 http://localhost:5173）
```

或只构建静态产物（输出到 `docs/.internal/.vitepress/dist`，可手动部署到私有目标）：

```bash
npm run docs:build:internal
```

组装由 `docs/scripts/internal-site.mjs` 完成，产物在 `docs/.internal/`（gitignored）；源文件仍是 `docs/site/`、`docs/internal/`、`docs/superpowers/` 三处，无重复副本。

## 本目录内容

- `team-sync.md`：团队同步汇报
- `usage.md`、`ai-integration.md`：公开内容迁移后的源文档
- `open-source-plan.md`：开源方案
- `architecture/`：总体架构、viewer 细节、路线图、现状评估
- `viewer/`：viewer 历史设计/API/计划文档
