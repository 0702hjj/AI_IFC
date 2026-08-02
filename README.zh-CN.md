# AI_IFC

[English](README.md)

自托管、开源的 **IFC 模型审查与编辑平台**——真改 IFC、语义化版本对比，以及人/AI 双角色共用的编辑 API。

> **文档站：<https://0702hjj.github.io/AI_IFC/>** ——快速开始、Viewer 使用、开发指南、REST/编辑 API 与 AI 接入。

## 功能

- 浏览器上传 IFC，三维审查属性、空间结构、Issue 与 3D 钉。
- 真实修改 IFC 属性（override → pending → commit），每次 commit 生成不可变版本快照。
- 按 GlobalId 的属性级语义 diff，在 Diff Viewer 中着色对比。
- 同一套 REST 编辑 API 开放给人与 AI（AI 直连时 `provenance.source="AI"`）。

## 快速开始

见文档站 [环境要求与本地部署](https://0702hjj.github.io/AI_IFC/guide/quickstart)。四个组件：`viewer/web`（React + xeokit）、`viewer/server`（Go）、`viewer/converter`（Node）、`viewer/edit-service`（Python FastAPI + IfcOpenShell）。

```bash
cd viewer/converter && npm install
cd ../edit-service && uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 &
cd ../server && go run ./cmd/server &
cd ../web && npm install && npm run dev
```

打开 http://localhost:5173 ，上传 `viewer/converter/test/fixtures/wall-with-opening-and-window.ifc` 验证。

## 仓库布局

```
viewer/            # 活跃产品：IFC 平台（web / server / converter / edit-service）
docs/site/         # 公开文档站（VitePress，发布到 GitHub Pages）
docs/internal/     # 内部计划与团队同步（不发布）
docs/archive/      # 归档的 SimpleCADAPI 文档
src/  skills/  examples/   # 归档：SimpleCADAPI（SCAD），仓库起点
```

## 许可证

[AGPL-3.0-only](LICENSE)——继承自 SimpleCADAPI fork，与 AGPL 的 xeokit 栈一致。三方组件与归档代码边界见 [NOTICE](NOTICE)。
