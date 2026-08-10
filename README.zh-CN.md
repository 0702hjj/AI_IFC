# AI_IFC

[English](README.md)

自托管、开源的 **IFC 模型审查与编辑平台**——script-as-source 编辑（一切修改落在 Python 构建脚本上）、语义化版本对比，以及设计师/AI 双角色共用的编辑 API。

> **文档站：<https://0702hjj.github.io/AI_IFC/>** ——快速开始、Viewer 使用、开发指南、REST/编辑 API 与 AI 接入。

## 核心优势

| | |
|---|---|
| **脚本即事实源编辑** | Python 构建脚本是 IFC 唯一事实源；web 端修改统一为改脚本（定位调用点 → PARAMS/libcst 改写 → 沙箱验证 → 暂存），每次保存生成不可变大版本（脚本 + ScriptMap 成对快照）。 |
| **语义版本对比** | 按 GlobalId 的属性级 diff（新增/删除/修改），Diff Viewer 展示 old → new 明细，无几何噪声。 |
| **一套 API，双角色** | 人与 AI 共用同一套 REST 编辑 API（人走 Go 代理，AI 直连并标记 `provenance.source="AI"`）。 |
| **AI 建模 skill** | agent 无关的 `aiifc` skill，让 AI 用自然语言驱动 `ifcopenshell.api` 代码生成或修改模型。 |
| **自托管、开源** | AGPL-3.0，四组件（web / server / converter / edit-service），文件或 PostgreSQL 存储，单机友好。 |

## 功能

- 浏览器上传 IFC，三维审查属性、空间结构、Issue 与 3D 钉。
- 修改 = 改构建脚本：查看器中选中构件定位脚本调用点，经 PARAMS 表单或脚本编辑器改写，沙箱验证后暂存；每次保存生成不可变大版本。
- 按 GlobalId 的属性级语义 diff，在 Diff Viewer 中着色对比。
- 同一套 REST 编辑 API 开放给人与 AI（AI 直连时 `provenance.source="AI"`）。
- 附带 AI 建模 skill（`skills/aiifc/`），让 agent 生成或大改 IFC 模型，与 REST 编辑 API 互补。

## 架构

```
浏览器 (React + xeokit) ──► Go server ──► edit-service (FastAPI + IfcOpenShell)
                                   │                └─ 脚本沙箱 + 版本 + diff
                                   ├─► converter (Node, IFC → XKT)
AI agent ──► REST 编辑 API ────────┘
          └─► aiifc skill（直接写 ifcopenshell.api 代码）
```

## 界面截图

| 模型库 | 三维查看器 |
|---|---|
| ![模型库](docs/site/public/screenshots/library.png) | ![三维查看器](docs/site/public/screenshots/viewer.png) |

| 属性编辑 | 版本对比 | AI 对话 |
|---|---|---|
| ![属性编辑](docs/site/public/screenshots/properties.png) | ![版本对比](docs/site/public/screenshots/diff.png) | ![AI 对话](docs/site/public/screenshots/chat.png) |

## 快速开始

见文档站 [环境要求与本地部署](https://0702hjj.github.io/AI_IFC/guide/quickstart)。四个组件：`viewer/web`（React + xeokit）、`viewer/server`（Go）、`viewer/converter`（Node）、`viewer/edit-service`（Python FastAPI + IfcOpenShell）。

一键启动（推荐，只需 Docker）：`docker compose up --build` → 打开 http://localhost:8080（可调项见 `.env.example`）。

手工启动：

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
| [REST 编辑 API](https://0702hjj.github.io/AI_IFC/reference/ai) | script-as-source 编辑：暂存/试运行/保存构建脚本，按 guid 定位调用点，libcst 标量改写（edit-call），带版本与 diff | `:8100/models/{id}/...` |
| [AI Skill (aiifc)](https://0702hjj.github.io/AI_IFC/reference/ai-skill) | 从零建模型 / 大改几何 | `skills/aiifc/`——agent 产出完整 Python **构建脚本**（顶层 `PARAMS` + `build()`），脚本与 IFC 一一对应、进版本、可 diff（script-as-source） |

skill 与 agent 无关（opencode、Claude Code、Cursor 等皆可）。打包分发包：

```bash
python tools/skill_pack_aiifc.py --archive   # 产出 skills/dist/aiifc.tar.gz
```

## 仓库布局

```
AGENTS.md          # 人机协同契约（AI agent 入口）
viewer/            # 活跃产品：IFC 平台（web / server / converter / edit-service / mcp-server）
skills/aiifc/      # AI 建模 skill（可分发包，agent 无关）——plan→DXF→IFC 管线的 IFC 段
AI_CAD/            # plan→DXF 段：aidxfv1（通用 DXF 生成/校验）/ aidxfv2（建筑平面管线）/ aiblueprint-mcp + 调研
tools/             # skill 打包器（skill_pack_aiifc.py）
docs/site/         # 公开文档站（VitePress，发布到 GitHub Pages）
docs/work/         # 工作项看板（审计/计划/可追踪工作项）
docs/internal/     # 内部团队文档（不发布）
docs/superpowers/  # 设计规范与实施计划（过程产物）
examples/          # IFC 时代示例脚本
```

SCAD 遗产代码（`src/`、`skills/simplecadapi/`、SCAD 时代打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不再包含。

## 许可证

[AGPL-3.0-only](LICENSE)——继承自 SimpleCADAPI fork，与 AGPL 的 xeokit 栈一致。三方组件与归档代码边界见 [NOTICE](NOTICE)。`skills/aiifc/` skill 本身声明为 **LGPL-3.0**（参考 LGPL 的 IfcOpenShell 官方文档）。
