# 仓库结构

```
AI_IFC/
├── viewer/                    # 活跃产品：IFC 审查与编辑平台
│   ├── web/                   # React 19 + xeokit 前端（:5173）
│   ├── server/                # Go 后端（:8090）
│   ├── converter/             # Node 转换器（IFC → XKT）
│   ├── edit-service/          # Python 编辑服务（:8100）
│   ├── scripts/smoke.sh       # 端到端冒烟
│   ├── data/                  # 运行时数据（gitignored）
│   └── docs/                  # 已并入公开文档站（本目录仅保留源码邻近说明）
├── docs/
│   ├── site/                  # 唯一公开文档站源（VitePress）
│   │   ├── .vitepress/config.mts
│   │   ├── index.md
│   │   ├── guide/  viewer/  development/  reference/  project/
│   │   └── public/            # favicon、ai-tools.openapi.json 等静态资源
│   ├── internal/              # 内部计划、团队同步、阶段评估（不发布）
│   ├── work/                  # 工作项看板（审计、计划、可跟踪条目）
│   └── superpowers/           # 设计规范与实施计划
├── research/                  # 调研笔记与目标映射（内部）
├── examples/                  # 归档：SCAD 示例
├── .github/workflows/         # CI（viewer）与 docs（构建 + Pages 部署）
├── LICENSE                    # AGPL-3.0-only
└── NOTICE                     # 三方组件与归档代码边界
```

> SCAD 遗产代码（`src/simplecadapi/`、`skills/simplecadapi/`、根打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不再包含。

## 文档边界

- `docs/site/` 是唯一公开文档站源，内容由 VitePress 构建并以 `/AI_IFC/` 为 base 发布到 GitHub Pages。
- `docs/internal/` 不进入站点导航与搜索（原 `docs/archive/` 已随 2026-08-05 清理移除，见 git 历史）。
- 各服务 README 只保留邻近源码的最小启动提示，详细说明一律链接到公开文档站。
