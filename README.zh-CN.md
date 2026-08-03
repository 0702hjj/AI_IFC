# AI_IFC

[English](README.md)

自托管、开源的 **IFC 模型审查与编辑平台**——真改 IFC、语义化版本对比，以及人/AI 双角色共用的编辑 API。

> **文档站：<https://0702hjj.github.io/AI_IFC/>** ——快速开始、Viewer 使用、开发指南、REST/编辑 API 与 AI 接入。

## 核心优势

| | |
|---|---|
| **真实编辑 IFC** | override → pending → commit 两阶段真改 IFC，每次 commit 生成不可变版本快照。 |
| **语义版本对比** | 按 GlobalId 的属性级 diff（新增/删除/修改），Diff Viewer 展示 old → new 明细，无几何噪声。 |
| **一套 API，双角色** | 人与 AI 共用同一套 REST 编辑 API（人走 Go 代理，AI 直连并标记 `provenance.source="AI"`）。 |
| **AI 建模 skill** | agent 无关的 `aiifc` skill，让 AI 用自然语言驱动 `ifcopenshell.api` 代码生成或修改模型。 |
| **自托管、开源** | AGPL-3.0，四组件（web / server / converter / edit-service），文件或 PostgreSQL 存储，单机友好。 |

## 功能

- 浏览器上传 IFC，三维审查属性、空间结构、Issue 与 3D 钉。
- 真实修改 IFC 属性（override → pending → commit），每次 commit 生成不可变版本快照。
- 按 GlobalId 的属性级语义 diff，在 Diff Viewer 中着色对比。
- 同一套 REST 编辑 API 开放给人与 AI（AI 直连时 `provenance.source="AI"`）。
- 附带 AI 建模 skill（`skills/aiifc/`），让 agent 生成或大改 IFC 模型，与 REST 编辑 API 互补。

## 架构

```
浏览器 (React + xeokit) ──► Go server ──► edit-service (FastAPI + IfcOpenShell)
                                   │                └─ 真改 IFC + 版本 + diff
                                   ├─► converter (Node, IFC → XKT)
AI agent ──► REST 编辑 API ────────┘
          └─► aiifc skill（直接写 ifcopenshell.api 代码）
```

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

## AI 接入：两条互补路径

| 路径 | 适用 | 入口 |
|---|---|---|
| [REST 编辑 API](https://0702hjj.github.io/AI_IFC/reference/ai) | 细粒度属性/属性集编辑，pending → commit，带版本与 diff | `:8100/models/{id}/...` |
| [AI Skill (aiifc)](https://0702hjj.github.io/AI_IFC/reference/ai-skill) | 从零建模型 / 大改几何 | `skills/aiifc/`——agent 直接写 `ifcopenshell.api` 代码 |

skill 与 agent 无关（opencode、Claude Code、Cursor 等皆可）。打包分发包：

```bash
python tools/skill_pack_aiifc.py --archive   # 产出 skills/dist/aiifc.tar.gz
```

## 仓库布局

```
viewer/            # 活跃产品：IFC 平台（web / server / converter / edit-service）
skills/aiifc/      # AI 建模 skill（可分发包，agent 无关）
tools/             # skill 打包器（skill_pack_aiifc.py）
docs/site/         # 公开文档站（VitePress，发布到 GitHub Pages）
docs/internal/     # 内部计划与团队同步（不发布）
docs/archive/      # 归档的 SimpleCADAPI 文档
src/  examples/    # 归档：SimpleCADAPI（SCAD），仓库起点
```

## 许可证

[AGPL-3.0-only](LICENSE)——继承自 SimpleCADAPI fork，与 AGPL 的 xeokit 栈一致。三方组件与归档代码边界见 [NOTICE](NOTICE)。`skills/aiifc/` skill 本身声明为 **LGPL-3.0**（参考 LGPL 的 IfcOpenShell 官方文档）。
