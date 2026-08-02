# AI_IFC 文档站增强：截图、双语扩展与 API 自动生成 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为公开文档站补齐三类增强：真实产品截图、VitePress 英文 locale（优先覆盖首页/快速开始/总体架构/贡献/API 入口）、edit-service API 参考页与 Go 端点清单的机器生成 + CI 漂移检测。

**Architecture:** 双语采用 VitePress `locales`（root=zh-CN 保持现有 URL，新增 `en` locale 于 `docs/site/en/`，参考 BotRS 的中英镜像组织）；API 自动生成采用"从已提交产物生成参考"策略——edit-service 参考页由 `docs/site/public/ai-tools.openapi.json` 生成，Go 端点清单由 `viewer/server/internal/api/*.go` 的 mux 注册扫描生成，两者都接入 `npm run check:api` + CI 漂移检测；截图在本地跑起四组件后用浏览器实拍，存 `docs/site/public/screenshots/`。

**Tech Stack:** VitePress 1.6（locales + local search）、Node 脚本（生成器）、GitHub Actions（新增 api-reference 漂移检查 job）、agent-browser（截图）、本地四组件栈（Go server / Node converter / React web / FastAPI edit-service）。

**来源规范：** `docs/superpowers/specs/2026-08-02-documentation-site-design.md` §9（后续迭代记录：9.1 双语扩展、9.2 API 自动生成、9.3 截图）；BotRS（YinMo19/botrs）docs 组织作为参考。

---

> **变更记录（2026-08-02）**：Task 6（产品截图）经用户确认后**取消**，本次迭代不实现截图；Task 7 的 Roadmap 更新与验收相应去掉截图项。其余任务（双语、API 自动生成）按计划完成。

## Global Constraints

- 工作分支 `iteration-docs-enhancements`，基于 main（PR #1/#2 均已合并）。
- 双语规则（spec §9.1）：英文只创建**真实内容**页，禁止空导航/占位页；英文优先覆盖首页、快速开始、总体架构、贡献、API 入口；未翻译页面在英文页中链接回中文页（允许，非占位）。
- 生成物规则：生成脚本必须**确定性输出**（无时间戳、稳定排序），生成文件提交入库；`check:api` 用 `git diff --exit-code` 检测漂移。
- 截图必须来自**真实运行的产品**（不允许造假图/占位图）；截图放 `docs/site/public/screenshots/`，经 `/screenshots/*.png` 引用。
- 公开构建（zh + en + 生成页）、内部 wiki 构建、`check:api`、现有 viewer CI 全部保持绿色。
- 中文源内容不因双语而丢失：zh 页面继续是信息权威；en 页面忠实翻译。
- 所有命令从声明的目录执行；`docs:` 前缀提交，每任务一次提交。

---

## Task 0: 分支与基线

**Files:**
- Modify: `.git`（创建分支，需提升权限）

- [ ] **Step 1: 确认工作区干净且在 main**

Run: `git status --porcelain && git branch --show-current`
Expected: 空输出 + `main`。

- [ ] **Step 2: 创建迭代分支**

Run（需批准）:

```bash
git switch -c iteration-docs-enhancements
```

Expected: `Switched to a new branch 'iteration-docs-enhancements'`。

- [ ] **Step 3: 基线构建确认**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`。

---

## Task 1: i18n 配置（locales）与英文首页

**Files:**
- Modify: `docs/site/.vitepress/config.mts`（改为 locales 结构）
- Modify: `docs/scripts/internal-site.mjs`（拷贝列表加 `en`，内部导航加英文入口）
- Create: `docs/site/en/index.md`

- [ ] **Step 1: 重写 `docs/site/.vitepress/config.mts` 为 locales 结构**

```ts
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/AI_IFC/',
  cleanUrls: true,
  lastUpdated: true,

  head: [
    ['meta', { name: 'theme-color', content: '#3fb950' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/AI_IFC/favicon.svg' }],
  ],

  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'AI_IFC',
      description: '自托管、开源的 IFC 审查与编辑平台',
      themeConfig: {
        nav: [
          { text: '快速开始', link: '/guide/project-intro' },
          { text: 'Viewer 使用', link: '/viewer/library' },
          { text: '开发指南', link: '/development/architecture' },
          { text: 'API 与 AI', link: '/reference/rest-api' },
          { text: '项目', link: '/project/roadmap' },
        ],

        sidebar: [
          {
            text: '快速开始',
            items: [
              { text: '项目介绍', link: '/guide/project-intro' },
              { text: '环境要求与本地部署', link: '/guide/quickstart' },
              { text: '上传第一个 IFC', link: '/guide/first-ifc' },
              { text: '配置说明', link: '/guide/configuration' },
            ],
          },
          {
            text: 'Viewer 使用',
            items: [
              { text: '模型库与模型上传', link: '/viewer/library' },
              { text: '模型树与属性检查', link: '/viewer/model-tree' },
              { text: '可见性、剖切与测量', link: '/viewer/viewing' },
              { text: 'Issue 与 3D Pin', link: '/viewer/issues' },
              { text: 'IFC 属性编辑', link: '/viewer/editing' },
              { text: '版本与 Diff Viewer', link: '/viewer/versions-diff' },
            ],
          },
          {
            text: '开发指南',
            items: [
              { text: '总体架构', link: '/development/architecture' },
              { text: '仓库结构', link: '/development/repo-structure' },
              { text: 'Web 前端', link: '/development/web' },
              { text: 'Go Server', link: '/development/server' },
              { text: 'IFC Converter', link: '/development/converter' },
              { text: 'Edit Service', link: '/development/edit-service' },
              { text: '测试与调试', link: '/development/testing' },
            ],
          },
          {
            text: 'API 与 AI',
            items: [
              { text: 'Viewer REST API', link: '/reference/rest-api' },
              { text: 'IFC 编辑 API', link: '/reference/edit-api' },
              { text: '编辑 API 参考（自动生成）', link: '/reference/edit-api-reference' },
              { text: 'AI 接入', link: '/reference/ai' },
              { text: 'OpenAPI 文件', link: '/reference/openapi' },
            ],
          },
          {
            text: '项目',
            items: [
              { text: 'Roadmap', link: '/project/roadmap' },
              { text: '已知限制', link: '/project/known-limits' },
              { text: '贡献指南', link: '/project/contributing' },
              { text: 'License 与第三方组件', link: '/project/license' },
            ],
          },
        ],

        search: {
          provider: 'local',
          options: {
            translations: {
              button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
              modal: {
                noResultsText: '未找到相关结果',
                resetButtonTitle: '清除查询条件',
                footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
              },
            },
          },
        },

        outline: { label: '本页目录', level: [2, 3] },
        lastUpdated: { text: '最后更新于' },
        docFooter: { prev: '上一篇', next: '下一篇' },
        returnToTopLabel: '返回顶部',
        sidebarMenuLabel: '菜单',
        darkModeSwitchLabel: '外观',
        lightModeSwitchTitle: '切换到浅色模式',
        darkModeSwitchTitle: '切换到深色模式',

        editLink: {
          pattern: 'https://github.com/0702hjj/AI_IFC/edit/main/docs/site/:path',
          text: '在 GitHub 上编辑此页',
        },

        socialLinks: [{ icon: 'github', link: 'https://github.com/0702hjj/AI_IFC' }],

        footer: {
          message: 'AGPL-3.0-only',
          copyright: 'Copyright © 2026 0702hjj',
        },
      },
    },

    en: {
      label: 'English',
      lang: 'en',
      title: 'AI_IFC',
      description: 'Self-hosted, open-source IFC review and editing platform',
      themeConfig: {
        nav: [
          { text: 'Quick Start', link: '/en/guide/project-intro' },
          { text: 'Architecture', link: '/en/development/architecture' },
          { text: 'API Reference', link: '/en/reference/rest-api' },
          { text: 'Contributing', link: '/en/project/contributing' },
        ],

        sidebar: [
          {
            text: 'Quick Start',
            items: [
              { text: 'Project Introduction', link: '/en/guide/project-intro' },
              { text: 'Environment & Local Deployment', link: '/en/guide/quickstart' },
              { text: 'Upload Your First IFC', link: '/en/guide/first-ifc' },
              { text: 'Configuration', link: '/en/guide/configuration' },
            ],
          },
          {
            text: 'Development',
            items: [
              { text: 'Architecture', link: '/en/development/architecture' },
            ],
          },
          {
            text: 'API & AI',
            items: [
              { text: 'Viewer REST API', link: '/en/reference/rest-api' },
              { text: 'IFC Editing API', link: '/en/reference/edit-api' },
              { text: 'Editing API Reference (generated)', link: '/reference/edit-api-reference' },
              { text: 'AI Integration', link: '/en/reference/ai' },
              { text: 'OpenAPI Files', link: '/en/reference/openapi' },
            ],
          },
          {
            text: 'Project',
            items: [
              { text: 'Contributing', link: '/en/project/contributing' },
            ],
          },
        ],

        search: { provider: 'local' },

        outline: { label: 'On this page', level: [2, 3] },
        lastUpdated: { text: 'Last updated' },
        docFooter: { prev: 'Previous', next: 'Next' },
        returnToTopLabel: 'Back to top',
        sidebarMenuLabel: 'Menu',
        darkModeSwitchLabel: 'Appearance',
        lightModeSwitchTitle: 'Switch to light mode',
        darkModeSwitchTitle: 'Switch to dark mode',

        editLink: {
          pattern: 'https://github.com/0702hjj/AI_IFC/edit/main/docs/site/:path',
          text: 'Edit this page on GitHub',
        },

        socialLinks: [{ icon: 'github', link: 'https://github.com/0702hjj/AI_IFC' }],

        footer: {
          message: 'AGPL-3.0-only',
          copyright: 'Copyright © 2026 0702hjj',
        },
      },
    },
  },
})
```

要点：root locale 的 URL 与现状完全一致（zh 页面路径不变）；`en` locale 页面位于 `docs/site/en/`，URL 前缀 `/en/`；VitePress 自动渲染语言切换菜单；生成页 `edit-api-reference` 在两个 locale 的侧边栏都出现（页面本身语言中立）。

- [ ] **Step 2: 更新 `docs/scripts/internal-site.mjs`**

把拷贝列表：

```js
for (const entry of ['index.md', 'guide', 'viewer', 'development', 'reference', 'project', 'public']) {
```

改为：

```js
for (const entry of ['index.md', 'guide', 'viewer', 'development', 'reference', 'project', 'public', 'en']) {
```

并在内部首页 `index.md` 模板的「公开内容」段落追加一行：

```markdown
- English docs: [Quick Start](/en/guide/project-intro)
```

- [ ] **Step 3: 创建 `docs/site/en/index.md`**

```markdown
---
layout: home

hero:
  name: AI_IFC
  text: IFC review and editing platform
  tagline: Self-hosted and open-source. Review IFC models in the browser, really edit attributes, compare versions with semantic diffs, and expose the same editing API to humans and AI.
  actions:
    - theme: brand
      text: Quick Start
      link: /en/guide/project-intro
    - theme: alt
      text: Upload your first IFC
      link: /en/guide/first-ifc

features:
  - title: 3D Review
    details: Upload an IFC and get fast XKT rendering; model tree, property inspection, section planes, measurements and 3D issue pins are built in.
  - title: Real Editing
    details: Property overrides and a two-phase pending → commit edit flow that really modifies IFC; every commit creates an immutable version snapshot.
  - title: Semantic Version Diff
    details: Attribute-level diffs keyed by GlobalId with added/removed/modified highlighting and old → new details, without geometric noise.
  - title: Human / AI Dual Role
    details: Humans and AI share the same REST editing API, distinguished by provenance; the OpenAPI tool catalog can be fed directly to an LLM.
---

## What it does

AI_IFC is an IFC (Industry Foundation Classes) review and editing platform made of four components:

- **web**: React + xeokit browser client for the model library, 3D review, property inspection, issues, property editing and version diffing.
- **server**: Go backend for uploads, the conversion queue, the REST API and edit orchestration, with file or PostgreSQL storage.
- **converter**: Node converter that turns IFC into XKT geometry and semantic metadata.
- **edit-service**: Python (FastAPI + IfcOpenShell) editing service for real IFC edits, version snapshots and semantic diffs.

Typical workflow: upload an IFC → review it in 3D once conversion finishes → file issues on elements → edit attributes (override or real edit) → commit to create a version → use Diff to compare versions.

## Getting started

1. [Project introduction](/en/guide/project-intro) — positioning, capability boundaries and the four-component architecture.
2. [Environment and local deployment](/en/guide/quickstart) — install dependencies and start all components in four terminals.
3. [Upload your first IFC](/en/guide/first-ifc) — run through review → issues → editing → diff with the bundled sample.
4. [Viewer REST API](/en/reference/rest-api) and [IFC editing API](/en/reference/edit-api) — API contracts; [AI integration](/en/reference/ai) for agents.

## Project status

The platform is functional end-to-end (upload → convert → review → edit → commit → diff). The active product is `viewer/`; SimpleCADAPI (SCAD) code from the repository history is kept as an archive, see [License & third-party components](/project/license) (Chinese) and [Roadmap](/project/roadmap) (Chinese).
```

- [ ] **Step 4: 验证构建**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0；dist 中同时存在 `index.html` 与 `en/index.html`。

- [ ] **Step 5: Commit**

```bash
git add docs/site/.vitepress/config.mts docs/site/en docs/scripts/internal-site.mjs
git commit -m "docs: add VitePress en locale (home page) and update internal-site assembly"
```

---

## Task 2: 英文快速开始分组（en/guide/）

**Files:**
- Create: `docs/site/en/guide/project-intro.md`
- Create: `docs/site/en/guide/quickstart.md`
- Create: `docs/site/en/guide/first-ifc.md`
- Create: `docs/site/en/guide/configuration.md`

- [ ] **Step 1: 创建 `docs/site/en/guide/project-intro.md`**

```markdown
# Project Introduction

AI_IFC is a **self-hosted, open-source** IFC model review and editing platform. It was forked from SimpleCADAPI, but the active product is the IFC platform under `viewer/`; SimpleCADAPI-related code is kept as an archive, see [License & third-party components](/project/license) (Chinese).

## Positioning

- **What it is**: a self-hosted IFC review + editing platform — real IFC attribute edits, semantic version diffing, and an editing API shared by humans and AI agents.
- **Who it is for**: self-hosted BIM teams (intranet or personal); developers building IFC tooling; researchers who need an "AI-pluggable BIM editing base".
- **Current capability**: functional end-to-end — upload → convert → 3D review → issues → property editing → commit → version diff.

## Capability boundaries

**Delivered:**

- IFC upload with queued conversion (XKT geometry + semantic metadata).
- 3D review: model tree, property inspection, visibility tools, section planes, measurements, NavCube.
- Issues and 3D pins: creation with camera state + screenshot, status workflow, click-to-locate.
- Property editing: whitelisted overrides (display layer) and the two-phase pending → commit real IFC edit flow.
- Version snapshots and attribute-level semantic diffs (Diff Viewer).
- One editing API shared by humans and AI, distinguished by `UI` / `AI` provenance.
- Optional PostgreSQL storage (issues / overrides / change log); file storage runs with zero external dependencies when unconfigured.

**Not delivered (see [Known limitations](/project/known-limits) and [Roadmap](/project/roadmap), Chinese):**

- Multi-user/auth; AI IFC generation itself; MCP wrapper; geometric diff; Docker Compose one-command deployment; fully bilingual site; automated OpenAPI generation (partially delivered, see [OpenAPI Files](/en/reference/openapi)).

## Four-component architecture

| Component | Tech | Responsibility |
| --- | --- | --- |
| `web` | React 19 + xeokit | Model library, 3D review, property editing, issues, Diff Viewer |
| `server` | Go 1.26 (stdlib + pgx/v5) | Upload/conversion queue, REST API, edit orchestration, storage abstraction |
| `converter` | Node CLI (web-ifc + xeokit-convert) | IFC → XKT + metadata.json |
| `edit-service` | Python FastAPI + IfcOpenShell + ifcdiff | Real IFC edits, pending/commit, version snapshots, semantic diffs |

The three-language stack is an ecosystem reality rather than a design preference: each language binds the only or best IFC library in that ecosystem. Services communicate over REST and subprocesses, and any component can be replaced independently.

Detailed architecture: [Architecture](/en/development/architecture).
```

- [ ] **Step 2: 创建 `docs/site/en/guide/quickstart.md`**

```markdown
# Environment & Local Deployment

## Dependencies

| Dependency | Version | Purpose | Required |
| --- | --- | --- | --- |
| Go | 1.26+ | server | yes |
| Node.js | 18+ | converter (`npm install` once, no daemon) | yes |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | for editing/diff; browsing works without it |
| PostgreSQL | 14+ | issues/changes/overrides persistence | optional (file storage by default) |
| IfcOpenShell source checkout | v0.8 | local editable dependency of ifcdiff | currently required (see below) |

> **ifcdiff dependency note**: `viewer/edit-service/pyproject.toml` currently references the IfcOpenShell source checkout (`src/ifcdiff`) next to this repo as a local editable dependency. Before running edit-service you need an IfcOpenShell v0.8 checkout in a sibling directory. This is a documented deployment limitation; self-containment (vendor or git source) is tracked in the [Roadmap](/project/roadmap) (Chinese).

## Start (four terminals)

```bash
# 0. One-time dependency install
cd viewer/converter && npm install
cd ../web && npm install
cd ../edit-service && uv sync

# 1. edit-service (:8100) — VIEWER_DATA_DIR must point to the absolute path of viewer/data
cd viewer/edit-service
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server (:8090)
cd viewer/server && go run ./cmd/server

# 3. web (:5173)
cd viewer/web && npm run dev
```

Open `http://localhost:5173` and you are ready. Full configuration: [Configuration](/en/guide/configuration).

## Verification

```bash
# End-to-end smoke (server must be running; the edit-flow section skips when edit-service is unreachable)
cd viewer && ./scripts/smoke.sh

# Per-layer tests
cd viewer/server && go test ./...
cd viewer/edit-service && uv run pytest
cd viewer/web && npm test
cd viewer/converter && npm test
```

> Note: upload, conversion and review do not need edit-service or PostgreSQL; editing, versions and diff do.
```

- [ ] **Step 3: 创建 `docs/site/en/guide/first-ifc.md`**

```markdown
# Upload Your First IFC

The repository bundles an official buildingSMART sample IFC:

`viewer/converter/test/fixtures/wall-with-opening-and-window.ifc`

## Workflow

1. **Upload**: drag an `.ifc` file (≤200MB; non-`.ifc` is rejected) onto the model library page. The model enters `converting`; the page polls every 2 seconds until it becomes `ready`. Failures show an error and can be retried.
2. **Open the model**: click the model to enter the 3D viewer. The model tree on the left expands one level by default and supports search, IFC-type filtering and per-node visibility; clicking an element highlights it and shows its property sets (psets) in the right panel.
3. **Review**: use the visibility toolbar (hide / isolate / X-Ray / reset), section sliders and distance measurement. Select an element to create an Issue (camera state and screenshot are captured automatically) and a 3D pin appears on the element.
4. **Edit**: in the property panel, the whitelisted fields (Name / Description / Classification / FireRating / Comments) can be edited inline and saved as overrides; see [IFC Property Editing](/viewer/editing) (Chinese) for details.
5. **Compare versions**: open **Diff** in the toolbar, choose base and target (a version or `current`) and run a semantic comparison; see [Versions & Diff Viewer](/viewer/versions-diff) (Chinese).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Stuck in converting | Check the converter stderr in server logs; run `node viewer/converter/convert.js <ifc> <outDir>` manually; verify `nodeBin` / `converterScript` |
| Conversion failed | Retry with `POST /api/models/{id}/retry` |
| Editing returns 404 model not found | `VIEWER_DATA_DIR` and the Go `dataDir` point to different directories |
| Editing returns 422 | Attribute name or value type is wrong — the request had no side effects, fix and resend |
| Commit returns 409 | No pending changes (pending lives in memory and is lost when edit-service restarts) |
| Attribute changes not reflected in the UI | Only Go-proxied commits trigger reconversion; direct edit-service calls need a manual refresh or a proxied replay |

The full troubleshooting table: [Testing & Debugging](/development/testing) (Chinese).
```

- [ ] **Step 4: 创建 `docs/site/en/guide/configuration.md`**

```markdown
# Configuration

## Go server (`viewer/server/server_config.json`)

Paths are resolved relative to the process working directory (not the executable).

| key | default | env override | description |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | listen address |
| `dataDir` | `../data` | — | data directory (**must equal edit-service's VIEWER_DATA_DIR**) |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | converter invocation |
| `maxUploadMB` | `200` | — | upload limit |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | enables PostgreSQL (auto-creates tables); empty = file storage |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service URL |

```json
{
  "host": "127.0.0.1",
  "port": 8090,
  "dataDir": "../data",
  "nodeBin": "node",
  "converterScript": "../converter/convert.js",
  "maxUploadMB": 200,
  "pgDSN": "",
  "editServiceURL": "http://127.0.0.1:8100"
}
```

## edit-service

| Environment variable | default | description |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | data directory (relative to the process working directory); **must point to the same directory as the server `dataDir`** or edits return 404 |
| `EDIT_SERVICE_PORT` | `8100` | listen port |

## PostgreSQL (optional)

- Without `pgDSN` / `VIEWER_PG_DSN`, issues / overrides / change log use file storage with zero external dependencies.
- When configured, the server auto-creates `issues` / `changes` / `overrides` tables at startup; model files (uploads / models / version snapshots) always stay on the filesystem.
- Tests need `VIEWER_TEST_PG_DSN` pointing to a **dedicated test database** (tests DROP tables).

## Ports

Defaults: server `8090`, edit-service `8100`, web dev server `5173`.
```

- [ ] **Step 5: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0；dist 含 `en/guide/project-intro.html` 等页面。

```bash
git add docs/site/en/guide
git commit -m "docs: add English quickstart section"
```

---

## Task 3: 英文总体架构与贡献（en/development + en/project）

**Files:**
- Create: `docs/site/en/development/architecture.md`
- Create: `docs/site/en/project/contributing.md`

- [ ] **Step 1: 创建 `docs/site/en/development/architecture.md`**

````markdown
# Architecture

```mermaid
graph LR
  subgraph Clients
    UI[Browser<br/>React 19 + xeokit<br/>viewer/web]
    AI[AI Agent]
  end

  subgraph Services
    GO[Go server :8090<br/>viewer/server<br/>orchestration / REST / storage abstraction]
    PY[Python edit-service :8100<br/>viewer/edit-service<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>viewer/converter<br/>IFC → XKT + metadata.json]
  end

  subgraph Storage
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(Filesystem<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|same editing API| PY
  AI -->|or via Go proxy| GO
  GO -->|/api/models/{id}/edit/* proxy + orchestration| PY
  GO -->|subprocess node convert.js| CV
  GO -->|pgx/v5, optional| PG
  GO --> FS
  PY -->|real IFC edits / version snapshots / history| FS
  CV -->|model.xkt + metadata.json| FS
```

## Component responsibilities

| Component | Tech | Responsibility | Why this tech |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | all review/edit/diff interaction | xeokit's XKT binary loading and BIM toolchain |
| server | Go 1.26 (stdlib net/http + pgx/v5) | upload/conversion queue, REST, edit orchestration, storage abstraction | static binary, concurrency model |
| converter | Node CLI (web-ifc + xeokit-convert) | IFC → XKT geometry + semantic extraction | xeokit-convert only ships as npm |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | real IFC edits, pending/commit, version snapshots, semantic diff | IfcOpenShell is the de-facto standard for IFC editing |
| PostgreSQL | optional | issues / changes / overrides tables | without `pgDSN` everything is file-based and dependency-free |

## Core data flows

### Upload and conversion

```
Browser upload .ifc → Go validates and stores uploads/{id}.ifc (status=converting)
  → conversion queue (2 workers, dedup + dirty rerun) → node convert.js
  → models/{id}/model.xkt (geometry) + metadata.json (spatial tree / psets)
  → status=ready → XKTLoaderPlugin loads geometry and semantics together
```

Key invariant: **XKT element id = metadata metaObject id = IFC GlobalId** — selection, highlighting and diff results all rely on this chain.

### Edit flow

```
PUT /models/{id}/entities/{guid}  {fields, psets, author, provenance}
  → full validation (any failure → 422, zero side effects) → apply to the in-memory model → record pending (with the real IFC oldValue)
POST /models/{id}/commit
  → atomic write (tmp+rename, per-model lock) → version snapshot versions/v{n+1}.ifc → append edit-history.json → clear pending
(via the Go proxy, orchestration continues:)
  → change log expanded per field (operation=update, diff filled by IfcDiff, non-fatal)
  → conversion queue reconverts XKT → frontend polls until ready and auto-reloads
```

### Versions and diff

- Before the first commit the original upload is copied to `versions/v1.ifc`; every commit snapshots `v{n+1}.ifc` (append-only).
- `POST /models/{id}/diff {base, target}`: IfcDiff (`relationships=["attributes","property"]`, geometry excluded by construction) yields added/removed sets; the adapter computes field-level old/new for changed entities; the result reduces to `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`.
- Snapshot-to-snapshot diff results are cached (versions are immutable, so the cache is naturally valid).

### Override → real-edit migration

```
Read all overrides → map per entity (Name/Description/Comments → fields;
  FireRating → look up the pset in metadata.json; Classification → try fields, 422 goes to failed)
→ one PUT (pending) per entity → one commit (operation=migrate)
→ successful fields clear their override; change log carries real old values; failed fields keep overrides with reasons
→ any success triggers reconversion
```

## Commit / version model

Change log entries carry: `author` (default `local-user`, no auth in v1), `createdAt` (UTC), `operation` (`update | migrate`), `diff` (filled by IfcDiff at commit), `provenance` (`{source: UI|AI}`, validated at the API layer). Versions form a linear snapshot sequence (branching/merging is out of scope, belongs to multi-user).

Known technical debt (details in [Known limitations](/project/known-limits), Chinese): three history records coexist (Go change log / edit-service edit-history / in-memory pending) with different granularity and purposes; ifcdiff is a local editable dependency; pending is in-memory; diff has no timeout; the Python side is file-storage only.
````

- [ ] **Step 2: 创建 `docs/site/en/project/contributing.md`**

```markdown
# Contributing

## Development environment

See [Environment & Local Deployment](/en/guide/quickstart). Development follows TDD: write a failing test first, then implement; tests live next to the source.

## Local verification

```bash
# backend
cd viewer/server && go test ./... && go vet ./...
# edit service
cd viewer/edit-service && uv run pytest
# frontend
cd viewer/web && npm test && npm run build
# converter
cd viewer/converter && npm test
# documentation (public site + API reference drift)
cd docs && npm ci && npm run docs:build && npm run check:api
```

## Documentation contributions

- The public site source lives in `docs/site/`, the single source of truth; after changes you must run `cd docs && npm run docs:build` (dead links fail the build).
- `docs/internal/` and `docs/archive/` are never part of the site — internal records and archives only.
- Pages that describe undelivered capabilities must be marked as Roadmap items and must not provide non-executable steps.
- After moving or archiving documents, update all Markdown relative links in the repository.
- Generated files (`docs/site/reference/edit-api-reference.md`, `docs/site/public/go-rest-api.routes.json`) must not be edited by hand; regenerate with `npm run gen:api` and commit the result. `npm run check:api` detects drift.
- To add an English page, create the real translated content under `docs/site/en/`; empty navigation or placeholder pages are not allowed.

## Commits and PRs

- Commit messages follow the repository convention: `feat:` / `fix:` / `docs:` / `ci:` / `chore:` prefix plus a short Chinese or English description.
- PRs to `main` run the viewer CI and the docs build; both must pass.
- Never commit personal machine paths, secrets or runtime data (`viewer/data/`).

## License

This repository is AGPL-3.0-only. Contributing means you agree to release your contribution under that license; third-party attributions: [License & third-party components](/project/license) (Chinese).
```

- [ ] **Step 3: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0；dist 含 `en/development/architecture.html` 与 `en/project/contributing.html`。

```bash
git add docs/site/en/development docs/site/en/project
git commit -m "docs: add English architecture and contributing pages"
```

---

## Task 4: 英文 API 分组（en/reference/）

**Files:**
- Create: `docs/site/en/reference/rest-api.md`
- Create: `docs/site/en/reference/edit-api.md`
- Create: `docs/site/en/reference/ai.md`
- Create: `docs/site/en/reference/openapi.md`
- Modify: `docs/site/reference/openapi.md`（中文页补机器可读产物说明）

- [ ] **Step 1: 创建 `docs/site/en/reference/rest-api.md`**

```markdown
# Viewer REST API

Backend base: `http://localhost:8090`; every JSON response uses the envelope `{code, message, data}` with `code=0` meaning success. Model ids look like `m_` + 16 lowercase hex characters.

## Models

### POST /api/models

Upload an IFC file and trigger asynchronous conversion. Request: `multipart/form-data`, field `file` (only `.ifc`, ≤200MB).

Response:

```json
{"code":0,"message":"ok","data":{"id":"m_01J...","name":"Building-Architecture.ifc","status":"converting"}}
```

Errors: `40001` invalid file type; `40002` over the size limit.

### GET /api/models

Model list (the frontend polls every 2s until all models leave `converting`):

```json
{"code":0,"message":"ok","data":[
  {"id":"m_01J...","name":"a.ifc","size":1832140,"status":"ready","createdAt":"2026-07-27T10:00:00Z","error":""}
]}
```

`status` ∈ `converting | ready | failed`.

### GET /api/models/{id} {#model-detail}

Single-model detail, same shape.

### POST /api/models/{id}/retry

Re-enqueue conversion for a `failed` model; returns the updated model object (`status:"converting"`).

### DELETE /api/models/{id} {#delete-model}

Deletes the model's IFC, XKT, metadata, state file and issues/changes/overrides. Response `data: null`.

### GET /api/models/{id}/download

Download the original IFC with `Content-Disposition: attachment; filename="<name>"`.

## Issues

Issue ids look like `i_` + 12 lowercase hex; `status` ∈ `open | checking | resolved`; `author` defaults to `local-user`; `provenance.source` defaults to `UI` (can be overridden at creation).

### GET /api/models/{id}/issues

Returns `data: Issue[]` ordered by createdAt descending.

### POST /api/models/{id}/issues

`multipart/form-data`:

- `issue` (required): JSON string `{"entityId","entityName","entityType","title","comment","author"?,"provenance"?,"camera":{"eye":[...],"look":[...],"up":[...]}}`; `title` is required.
- `screenshot` (optional): PNG file, ≤5MB.

Returns `data: Issue` (with the generated id, `status:"open"`, default author/provenance, `screenshot` relative path, createdAt/updatedAt).

### PATCH /api/models/{id}/issues/{issueId} {#patch-issue}

JSON body: `{"title"?, "comment"?, "status"?}` — only the given fields are updated.

### DELETE /api/models/{id}/issues/{issueId} {#delete-issue}

Deletes the issue and its screenshot.

### GET /models/{id}/issues/{file}

Issue screenshot static service; `file` must match `i_[0-9a-f]{12}\.png`.

## Property overrides and change log

Property edits go through metadata overrides (the IFC itself is untouched): whitelisted fields are exactly `Name / Description / Classification / FireRating / Comments`; every change writes one change log entry per field.

### GET /api/models/{id}/overrides

Returns `data: { [entityId]: { [field]: value } }` (`{}` when empty).

### PUT /api/models/{id}/entities/{entityId}/properties

JSON body: `{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"note"}}`.

- `fields` is required and non-empty; a name outside the whitelist returns `40001 field not in whitelist`.
- An empty string clears that field's override.
- Every field writes a change log entry (oldValue is the previously effective value; author `local-user`; provenance `UI`).
- Returns `data: { [field]: value }`, the entity's current effective overrides.

### GET /api/models/{id}/changes

Returns `data: ChangeEntry[]` ordered by createdAt descending (`[]` when empty):

```json
{"code":0,"message":"ok","data":[
  {"id":"c_1a2b3c4d5e6f","entityId":"3a82-xxxx","entityName":"Wall","field":"FireRating","oldValue":"","newValue":"F60","author":"local-user","provenance":{"source":"UI"},"operation":"update","createdAt":"2026-07-29T10:00:00Z"}
]}
```

## Edit proxy endpoints

The Go server exposes the edit-service endpoints under the `/api/models/{id}/edit/...` prefix (orchestration: after commit it writes the change log, fills diffs via IfcDiff and queues XKT reconversion). Full contract: [IFC Editing API](/en/reference/edit-api).

## Static resources (no envelope)

| Path | Description |
| --- | --- |
| `GET /models/{id}/model.xkt` | XKT geometry (supports Range) |
| `GET /models/{id}/metadata.json` | metadata (below) |
| `GET /models/{id}/issues/{file}` | issue screenshots |

## metadata.json Schema (xeokit meta-model format)

Extracted from the original IFC by the converter (spatial tree + property sets), directly usable as `XKTLoaderPlugin.load({metaModelSrc})`:

```json
{
  "projectId": "3xFoo",
  "metaObjects": [
    {"id": "1AbC...", "type": "IfcBuildingStorey", "name": "Level 1", "parent": "0Root"},
    {"id": "2XdE...", "type": "IfcWall", "name": "Wall-001", "parent": "1AbC...", "propertySetIds": ["pset_2XdE_0"]}
  ],
  "propertySets": [
    {
      "id": "pset_2XdE_0",
      "name": "Pset_WallCommon",
      "type": "Pset",
      "properties": [
        {"name": "FireRating", "value": "120min", "type": "IfcLabel"},
        {"name": "LoadBearing", "value": true, "type": "IfcBoolean"}
      ]
    }
  ]
}
```

Conventions: `metaObjects[].id` is the IFC GlobalId (identical to the XKT entity id); hierarchy is Site → Building → Storey → element; elements without psets omit `propertySetIds`.

## Common error codes

`40001` parameter/validation error, `40002` over limit, `40400` model or issue not found, `50000` internal server error.
```

- [ ] **Step 2: 创建 `docs/site/en/reference/edit-api.md`**

```markdown
# IFC Editing API

The edit-service (Python FastAPI, default `:8100`) is the **single reference** for IFC editing endpoints. Path parameters: `id` matches `^m_[0-9a-f]{16}$`; `guid` is an IFC GlobalId. Unless noted, error responses use the FastAPI shape `{"detail": ...}`.

## Endpoint catalog

### GET /health

Health check, responds `{"status": "ok"}`.

### PUT /models/{id}/entities/{guid}

Applies an edit to the in-memory model and records one pending change (**no disk write**). Full validation happens before any application (atomic per request): any failure produces zero modifications.

Body (`EditBody`):

```json
{
  "type": "object",
  "properties": {
    "fields": {"type": "object", "additionalProperties": true, "description": "direct entity attributes (Name/Description etc.)"},
    "psets": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": true}, "description": "pset name → {attribute: new value}; psets are created when missing"},
    "author": {"type": "string", "default": "local-user"},
    "provenance": {"type": "object", "properties": {"source": {"type": "string", "enum": ["UI", "AI"], "default": "UI"}}}
  }
}
```

Response 200 (a pending entry that also appears in pending and in history after commit):

```json
{
  "id": "e_<12hex>",
  "guid": "...",
  "changes": [{"field": "Name", "oldValue": "...", "newValue": "..."}],
  "author": "ai-agent",
  "provenance": {"source": "AI"},
  "timestamp": "<ISO8601 UTC>"
}
```

`changes[].field`: direct attributes use the attribute name; pset attributes use `PsetName.attribute`; `oldValue` is the real IFC value (`null` when the pset attribute did not exist).

Error codes: 404 model or guid not found; 422 both `fields`/`psets` empty, unknown attribute, unsupported value type, or a type mismatch with the IFC attribute.

### GET /models/{id}/pending

Lists current pending changes (`[]` when empty). Note: GET pending/history **do not validate the model**; write paths and versions/diff do.

### DELETE /models/{id}/pending

Discards all pending changes: unloads and reloads the model from disk. Responds `{"discarded": <count>}`; 404 when the model does not exist.

### POST /models/{id}/commit

Atomically writes all pending changes (file lock) → version snapshot → appends history (each entry gets `operation`) → clears pending.

Optional body: `{"operation": "update" | "migrate"}`, default `"update"`; `migrate` is passed by the Go override migration. Response 200 `{"committed": <count>, "entries": [...]}`; 409 without pending; 404 when the model does not exist.

### GET /models/{id}/history

Persistence editing history (includes `operation`), stored at `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`; `[]` when empty.

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

Before any commit `versions` is `[]` and `current` is `null`.

### POST /models/{id}/diff

Body: `{"base": "v1", "target": "v2"}` (`target` may be `"current"` for the live upload). Response:

```json
{
  "base": "v1",
  "target": "v2",
  "added": ["<guid>", ...],
  "removed": ["<guid>", ...],
  "changed": [{"guid": "...", "changes": [{"field": "...", "old": ..., "new": ...}]}]
}
```

Missing version → 404; missing `base`/`target` → 422. Diff is attribute-level (no geometric diff), see [Versions & Diff Viewer](/viewer/versions-diff) (Chinese).

## Via the Go proxy

The Go server (default `:8090`) exposes the same endpoints under `/api/models/{id}/edit/...`, one-to-one:

| Go proxy endpoint | Python endpoint |
| --- | --- |
| `PUT /api/models/{id}/edit/entities/{guid}` | `PUT /models/{id}/entities/{guid}` |
| `GET /api/models/{id}/edit/pending` | `GET /models/{id}/pending` |
| `DELETE /api/models/{id}/edit/pending` | `DELETE /models/{id}/pending` |
| `GET /api/models/{id}/edit/history` | `GET /models/{id}/history` |
| `GET /api/models/{id}/edit/versions` | `GET /models/{id}/versions` |
| `POST /api/models/{id}/edit/diff` | `POST /models/{id}/diff` |
| `POST /api/models/{id}/edit/commit` | `POST /models/{id}/commit` |

Differences from direct access:

- Responses are wrapped in `{code, message, data}`; error mapping: 404 → 40400, 409 → 40900, 422 → 40001, anything else (including unreachable) → 50200.
- If a PUT/commit body contains `provenance.source`, Go validates the enum (UI|AI) first; invalid → 40001.
- After a Go-proxied commit: entries are expanded into the change log, `diff` is filled by IfcDiff, the model goes `converting` and reconversion is queued; the response data additionally contains `"reconverting": true`.
- A change-log write failure does not return 500: it is logged, the response stays 200 with a `"warning"` string (the IFC is persisted and reconversion is queued; only the change log may be missing entries).
```

- [ ] **Step 3: 创建 `docs/site/en/reference/ai.md`**

```markdown
# AI Integration

An integration guide for AI agents: use REST to drive the IFC editing service through the full "edit attribute → pending → commit → diff" flow. The machine-consumable schema: [OpenAPI Files](/en/reference/openapi).

## One API, two roles

Humans (browser) and AI agents use the **same editing endpoints**; only the entry point and `provenance.source` differ:

```
Browser (human) ──► Go server :8090 ──proxy──► Python edit-service :8100
                  /api/models/{id}/edit/...        │  /models/{id}/...
AI agent ────────► REST direct ────────────────────┘  (or via the Go proxy, one-to-one)
```

- Human: browser → Go proxy; after commit Go writes the change log and triggers XKT reconversion.
- AI: REST directly to edit-service (default `http://127.0.0.1:8100`) with `provenance.source="AI"`; the Go proxy works too.
- The Python service ships Swagger UI (`/docs`) and the raw schema (`/openapi.json`).

## Quick start

```bash
# 1) Python edit service (default port 8100)
cd viewer/edit-service
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server (default 127.0.0.1:8090)
cd viewer/server
go run ./cmd/server
```

**dataDir consistency**: `VIEWER_DATA_DIR` must point to the same directory as the Go `server_config.json` `dataDir` (both locate model files at `{dataDir}/uploads/{id}.ifc`).

## Direct AI flow (curl)

Prerequisite: a model exists (id like `m_` + 16 lowercase hex) with its file at `{VIEWER_DATA_DIR}/uploads/{id}.ifc`.

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef
GUID='2O2Fr$t4X7ZfFPoeewFlqU'   # IFC GlobalId

# 1. Edit attribute → pending (in-memory only, no disk write)
curl -X PUT "$BASE/models/$MID/entities/$GUID" \
  -H 'Content-Type: application/json' \
  -d '{
        "fields": {"Name": "Basic Wall:AI"},
        "psets":  {"Pset_WallCommon": {"FireRating": "2h"}},
        "author": "ai-agent",
        "provenance": {"source": "AI"}
      }'

# 2. Inspect pending
curl "$BASE/models/$MID/pending"

# 3. Commit: atomic write + version snapshot + history
curl -X POST "$BASE/models/$MID/commit"

# 4. Versions and diff
curl "$BASE/models/$MID/versions"
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' \
  -d '{"base": "v1", "target": "current"}'
```

> A direct commit does **not** trigger the Go change log or XKT reconversion. For the full pipeline (visible to the frontend) use the Go proxy: `http://127.0.0.1:8090/api/models/$MID/edit/...`.

## Provenance and the commit model

- `provenance.source`: enum `UI | AI`, default `UI`. **AI calls must pass `"AI"`**. It is a declared field without anti-forgery semantics (no auth in v1).
- `author`: free text, default `local-user`.
- Two-phase semantics: PUT only changes the in-memory model and records pending; commit persists to disk, creates a version snapshot and writes history.
- Commit model (Go change log): each entry has `author` / `createdAt` / `operation` (`update | migrate`) / `diff` / `provenance`.
- Python history and the Go change log are two records: history = one entry per PUT (with a changes array); change log = one entry per field change.

## Versions and diff semantics

- Snapshots live at `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc` (n from 1, append-only, atomic writes).
- First commit: the original upload is snapshotted as v1, then the new file as v2; every later commit produces v{n+1}.
- Diff is keyed by GlobalId; changed entities reduce to field-level old→new for direct and pset attributes; entity reference attributes (geometry representation) are excluded.
- Snapshot-to-snapshot diff results are cached in `versions/diff-{base}-{target}.json`; `target="current"` is not cached.

## Limits and roadmap

v1 limits (details in [Known limitations](/project/known-limits), Chinese): single-machine single-user, no auth (do not expose publicly); pending is in-memory (lost on service restart); `VIEWER_DATA_DIR` must equal the Go `dataDir`; diff is attribute-level only.

Roadmap (not delivered yet): an MCP wrapper (REST+MCP dual exposure, modeled on ifcmcp's tool patterns) and a sandbox/execution endpoint — see [Roadmap](/project/roadmap) (Chinese).
```

- [ ] **Step 4: 创建 `docs/site/en/reference/openapi.md`**

```markdown
# OpenAPI Files

## edit-service (machine-consumable)

The full OpenAPI schema: [ai-tools.openapi.json](/ai-tools.openapi.json), exported directly from the implementation (`create_app().openapi()`), identical to the live `GET /openapi.json`.

Regenerate after editing the editing API:

```bash
cd viewer/edit-service
uv run python scripts/export_openapi.py
```

The script writes `docs/site/public/ai-tools.openapi.json` (published with the site's public directory).

The page [Editing API Reference (generated)](/reference/edit-api-reference) is generated from that schema by `docs/scripts/gen-edit-api-reference.mjs`; run `npm run gen:api` after any schema change and commit the result. `npm run check:api` fails when committed output drifts.

## Go server

The Go server's REST contract is documented by hand at [Viewer REST API](/en/reference/rest-api). A machine-readable endpoint inventory is generated from the Go mux registrations: [go-rest-api.routes.json](/go-rest-api.routes.json) (method, path, handler, source file). Full request/response schema generation for Go remains a follow-up.

> Automated page generation from schemas and CI drift detection are partially delivered (see above); code-vs-schema drift detection for edit-service needs the ifcdiff dependency to become self-contained first (see [Roadmap](/project/roadmap), Chinese).
```

- [ ] **Step 5: 更新中文 `docs/site/reference/openapi.md`**

在「Go server」一节替换为：

````markdown
## Go server

Go server 的 REST 契约当前以本文档站 [Viewer REST API](/reference/rest-api) 为人工维护的公开契约。另提供从 Go mux 注册扫描生成的**机器可读端点清单**：[go-rest-api.routes.json](/go-rest-api.routes.json)（method / path / handler / 源文件），由 `docs/scripts/gen-go-routes.mjs` 生成，`npm run check:api` 检测漂移；Go 侧请求/响应 schema 的完整自动生成仍属后续迭代。

> 自动生成与漂移检测已部分落地：edit-service 的字段/端点参考页由 OpenAPI schema 生成（见 [编辑 API 参考（自动生成）](/reference/edit-api-reference)）；edit-service 的"代码 vs schema"漂移检测需待 ifcdiff 依赖自包含后才能接入（见 [Roadmap](/project/roadmap)）。
````

- [ ] **Step 6: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0；dist 含 `en/reference/rest-api.html` 等 4 页。

```bash
git add docs/site/en/reference docs/site/reference/openapi.md
git commit -m "docs: add English API section and note machine-readable Go contract"
```

---

## Task 5: API 自动生成（脚本 + CI 漂移检测 + 生成物）

**Files:**
- Create: `docs/scripts/gen-edit-api-reference.mjs`
- Create: `docs/scripts/gen-go-routes.mjs`
- Modify: `docs/package.json`（`gen:api` / `check:api`）
- Modify: `.github/workflows/docs.yml`（新增 `api-reference` job）
- Create（生成物，提交入库）: `docs/site/reference/edit-api-reference.md`、`docs/site/public/go-rest-api.routes.json`

- [ ] **Step 1: 创建 `docs/scripts/gen-edit-api-reference.mjs`**

````js
#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
//
// Generate docs/site/reference/edit-api-reference.md from the committed OpenAPI
// schema at docs/site/public/ai-tools.openapi.json (exported from the FastAPI
// edit-service by viewer/edit-service/scripts/export_openapi.py).
// Deterministic output: stable sorting, no timestamps.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const docsRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const schemaPath = join(docsRoot, 'site', 'public', 'ai-tools.openapi.json')
const outPath = join(docsRoot, 'site', 'reference', 'edit-api-reference.md')

const schema = JSON.parse(readFileSync(schemaPath, 'utf8'))
const out = []
out.push('# 编辑 API 参考（自动生成）', '')
out.push(
  '> 本页由 `docs/scripts/gen-edit-api-reference.mjs` 从 `docs/site/public/ai-tools.openapi.json` 自动生成，**请勿手工编辑**。',
  '> 源 schema 由 edit-service 导出（`viewer/edit-service/scripts/export_openapi.py`）；工作流与语义解释见 [IFC 编辑 API](/reference/edit-api)。',
  ''
)
out.push(`- 服务：${schema.info?.title ?? 'ifc-edit-service'} ${schema.info?.version ?? ''}`)
out.push(`- OpenAPI 版本：${schema.openapi ?? ''}`)
if (schema.servers?.length) {
  out.push(`- 默认地址：${schema.servers.map((s) => s.url).join(', ')}`)
}
out.push('', '## 端点', '')

const paths = Object.keys(schema.paths || {}).sort()
if (paths.length === 0) out.push('（无端点）')
for (const p of paths) {
  const methods = Object.keys(schema.paths[p])
    .filter((m) => ['get', 'post', 'put', 'patch', 'delete'].includes(m))
    .sort()
  for (const m of methods) {
    const op = schema.paths[p][m]
    out.push(`### ${m.toUpperCase()} ${p}`, '')
    if (op.summary) out.push(op.summary, '')
    if (op.description) out.push(op.description, '')
    const params = op.parameters || []
    if (params.length) {
      out.push('参数：', '', '| 名称 | 位置 | 必填 | 类型 | 说明 |', '| --- | --- | --- | --- | --- |')
      for (const pa of params) {
        out.push(
          `| \`${pa.name}\` | ${pa.in} | ${pa.required ? '是' : '否'} | ${pa.schema?.type ?? ''} | ${(pa.description ?? '').replace(/\|/g, '\\|')} |`
        )
      }
      out.push('')
    }
    const rb = op.requestBody?.content?.['application/json']?.schema
    if (rb) {
      out.push('请求体（application/json）：', '', '```json', JSON.stringify(rb, null, 2), '```', '')
    }
    const codes = Object.keys(op.responses || {}).sort()
    if (codes.length) {
      out.push('响应：', '', '| 状态码 | 说明 |', '| --- | --- |')
      for (const c of codes) {
        out.push(`| ${c} | ${(op.responses[c].description ?? '').replace(/\|/g, '\\|')} |`)
      }
      out.push('')
    }
  }
}

const components = schema.components?.schemas || schema['$defs'] || {}
const names = Object.keys(components).sort()
if (names.length) {
  out.push('## 组件 Schema', '')
  for (const n of names) {
    out.push(`### ${n}`, '', '```json', JSON.stringify(components[n], null, 2), '```', '')
  }
}

writeFileSync(outPath, out.join('\n') + '\n', 'utf8')
console.log(`wrote ${outPath}`)
````

- [ ] **Step 2: 创建 `docs/scripts/gen-go-routes.mjs`**

```js
#!/usr/bin/env node
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
//
// Generate docs/site/public/go-rest-api.routes.json from the Go server's mux
// registrations (viewer/server/internal/api/{api,edit}.go). Deterministic.
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const apiDir = join(repoRoot, 'viewer', 'server', 'internal', 'api')
const outPath = join(repoRoot, 'docs', 'site', 'public', 'go-rest-api.routes.json')

const files = ['api.go', 'edit.go']
const endpointRe = /mux\.HandleFunc\(\s*"([A-Z]+)\s+([^"]+)"\s*,\s*(\w+)\)/g
const endpoints = []
for (const f of files) {
  const src = readFileSync(join(apiDir, f), 'utf8')
  for (const m of src.matchAll(endpointRe)) {
    endpoints.push({ method: m[1], path: m[2], handler: m[3], file: `viewer/server/internal/api/${f}` })
  }
}
endpoints.sort((a, b) => a.path.localeCompare(b.path) || a.method.localeCompare(b.method))

const contract = {
  service: 'viewer server (Go)',
  source: 'viewer/server/internal/api/{api,edit}.go',
  generatedBy: 'docs/scripts/gen-go-routes.mjs',
  note: 'Machine-readable endpoint inventory extracted from Go mux registrations. Human-readable contract: docs/site/reference/rest-api.md.',
  endpoints,
}
writeFileSync(outPath, JSON.stringify(contract, null, 2) + '\n', 'utf8')
console.log(`wrote ${outPath} (${endpoints.length} endpoints)`)
```

- [ ] **Step 3: 更新 `docs/package.json`**

在 scripts 中追加：

```json
    "gen:api": "node scripts/gen-edit-api-reference.mjs && node scripts/gen-go-routes.mjs",
    "check:api": "npm run gen:api && git -C .. diff --exit-code -- docs/site/reference/edit-api-reference.md docs/site/public/go-rest-api.routes.json"
```

- [ ] **Step 4: 生成并提交生成物**

Run（docs/）: `npm run gen:api`
Expected: `wrote .../edit-api-reference.md` 与 `wrote .../go-rest-api.routes.json (N endpoints)`。

检查：`git -C .. status --porcelain` 应显示两个新文件；`npm run check:api` 退出码 0（生成后无 diff）。

- [ ] **Step 5: 更新 `.github/workflows/docs.yml`**

在 `jobs:` 下新增 job（放在 `build` 之后）：

```yaml
  api-reference:
    name: API reference drift check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: docs/package-lock.json
      - run: npm ci
        working-directory: docs
      - run: npm run check:api
        working-directory: docs
```

- [ ] **Step 6: 验证**

Run（docs/）: `npm run docs:build && npm run check:api`
Expected: build 退出码 0；`check:api` 无 diff（退出码 0）。

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml')); print('yaml ok')"`
Expected: `yaml ok`。

- [ ] **Step 7: Commit**

```bash
git add docs/scripts docs/package.json .github/workflows/docs.yml docs/site/reference/edit-api-reference.md docs/site/public/go-rest-api.routes.json
git commit -m "docs: generate API reference pages and add CI drift check"
```

---

## Task 6: 产品截图

> **已取消（2026-08-02，用户决定不做）**：原计划拍摄模型库/三维审查/Diff 三张真实截图并嵌入页面。本次迭代不执行本任务；如后续需要，可单独立项。

**Files:**
- Create（运行产物，提交入库）: `docs/site/public/screenshots/library.png`、`viewer.png`、`diff.png`
- Modify: `docs/site/guide/first-ifc.md`、`docs/site/en/guide/first-ifc.md`、`docs/site/viewer/versions-diff.md`（嵌入截图）

- [ ] **Step 1: 读取 agent-browser 技能说明**

Read: `/home/hjj0702/.agents/skills/agent-browser/SKILL.md`
Expected: 了解截图与点击命令用法（`agent-browser open/screenshot/click/read` 等）。

- [ ] **Step 2: 启动四组件栈（本机）**

Run（仓库根，需批准后台进程与网络）:

```bash
cd viewer/edit-service && VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 > /tmp/es.log 2>&1 &
cd ../server && go run ./cmd/server > /tmp/server.log 2>&1 &
cd ../web && npm run dev -- --host 127.0.0.1 > /tmp/web.log 2>&1 &
```

Expected: 三个进程就绪；`curl -sf http://127.0.0.1:8090/api/models` 与 `curl -sf http://127.0.0.1:8100/health` 返回 200。

- [ ] **Step 3: 上传样例并制造版本**

Run（仓库根）:

```bash
ID=$(curl -sf -F "file=@viewer/converter/test/fixtures/wall-with-opening-and-window.ifc" http://127.0.0.1:8090/api/models | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["id"])')
for i in $(seq 1 60); do
  ST=$(curl -sf http://127.0.0.1:8090/api/models/$ID | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
  [ "$ST" = "ready" ] && break; sleep 2
done
echo "model=$ID status=$ST"
GUID=$(curl -sf http://127.0.0.1:8090/models/$ID/metadata.json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["metaObjects"][-1]["id"])')
curl -sf -X PUT -H 'Content-Type: application/json' \
  -d "{\"fields\":{\"Name\":\"Wall:Demo\"},\"author\":\"demo\",\"provenance\":{\"source\":\"UI\"}}" \
  http://127.0.0.1:8090/api/models/$ID/edit/entities/$GUID > /dev/null
curl -sf -X POST http://127.0.0.1:8090/api/models/$ID/edit/commit > /dev/null
for i in $(seq 1 60); do
  ST2=$(curl -sf http://127.0.0.1:8090/api/models/$ID | python3 -c 'import sys,json;print(json.load(sys.stdin)["data"]["status"])')
  [ "$ST2" = "ready" ] && break; sleep 2
done
echo "after commit status=$ST2 versions=$(curl -sf http://127.0.0.1:8090/api/models/$ID/edit/versions)"
```

Expected: `status=ready`；commit 后 `versions` 返回含 v1/v2；模型可访问 `http://127.0.0.1:5173/view/$ID`。

- [ ] **Step 4: 截图三张**

Run（使用 agent-browser 技能）:

```bash
mkdir -p docs/site/public/screenshots
agent-browser open "http://127.0.0.1:5173/"        # 模型库页（含已上传模型）→ screenshot library.png
agent-browser open "http://127.0.0.1:5173/view/$ID" # 三维审查（树+属性可见）→ screenshot viewer.png
agent-browser open "http://127.0.0.1:5173/view/$ID" # 打开 Diff 面板选 v1/current 对比 → screenshot diff.png
```

Expected: 三张 PNG 生成于 `docs/site/public/screenshots/`，肉眼检查非空白、界面真实（模型渲染、面板可见）。

- [ ] **Step 5: 嵌入页面**

中文 `docs/site/guide/first-ifc.md`「操作流程」前插入：

````markdown
## 界面预览

![模型库](/screenshots/library.png)

![三维审查](/screenshots/viewer.png)
````

英文 `docs/site/en/guide/first-ifc.md` 同样位置插入：

````markdown
## Screenshots

![Model library](/screenshots/library.png)

![3D review](/screenshots/viewer.png)
````

中文 `docs/site/viewer/versions-diff.md`「Diff 面板」节末追加：

````markdown
![Diff Viewer](/screenshots/diff.png)
````

- [ ] **Step 6: 验证构建 + 停服务 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0（图片资源经 `/screenshots/*.png` 正确打包）。

Run（仓库根）: `kill %1 %2 %3 2>/dev/null; true`（清理后台进程）

```bash
git add docs/site/public/screenshots docs/site/guide/first-ifc.md docs/site/en/guide/first-ifc.md docs/site/viewer/versions-diff.md
git commit -m "docs: add product screenshots (library, viewer, diff)"
```

---

## Task 7: Roadmap 更新、总体验收与 PR

**Files:**
- Modify: `docs/site/project/roadmap.md`
- Modify: `docs/internal/architecture/roadmap.md`

- [ ] **Step 1: 更新公开 Roadmap `docs/site/project/roadmap.md`**

「已完成」追加（不含截图）：

```markdown
- 文档增强：英文 locale（首页、快速开始、总体架构、贡献、API 入口）、edit-service API 参考页与 Go 端点清单的机器生成 + CI 漂移检测。
```

「后续」改为：

```markdown
- **双语扩展（后续）**：其余页面（Viewer 使用、开发指南细节、项目组）的英文版本。
- **API 自动生成（后续）**：edit-service 的"代码 vs schema"漂移检测（需 ifcdiff 依赖自包含）；Go server 请求/响应 schema 的完整自动生成。
```

- [ ] **Step 2: 更新内部 Roadmap `docs/internal/architecture/roadmap.md`**

在「后续任务（文档站确认，2026-08-02）」一节追加：

```markdown
- 已完成（2026-08-02）：英文 locale 优先集（首页/快速开始/总体架构/贡献/API 入口）、产品截图、edit-service API 参考页 + Go 端点清单生成与 CI 漂移检测。
- 仍待办：edit-service 代码 vs schema 漂移检测（ifcdiff 自包含后）、Go server 完整 schema 生成、英文剩余页面。
```

- [ ] **Step 3: 干净构建总验收**

Run（docs/）:

```bash
rm -rf node_modules .vitepress/dist .internal
npm ci
npm run docs:build
npm run docs:build:internal
npm run check:api
```

Expected: 全部退出码 0；`docs:build` 产物含 zh + en 全部页面；`docs:build:internal` 通过；`check:api` 无 diff。

- [ ] **Step 4: 验收核对**

| 项 | 核对 |
| --- | --- |
| 英文无占位页 | `rg -n "TODO|TBD|占位" docs/site/en` 无命中；`find docs/site/en -name '*.md'` 恰为 11 页 |
| 双语导航完整 | 构建产物含 `/AI_IFC/en/index.html` 且 en 页链接均 200（预览抽查） |
| API 生成确定性 | 连续两次 `npm run gen:api` 后 `git diff` 为空 |
| 截图真实 | `file docs/site/public/screenshots/*.png` 为 PNG；页面引用路径存在 |
| 公开构建 + 内部构建 + viewer CI | 本地两构建通过；PR 上 docs build / api-reference / viewer CI 全绿 |

- [ ] **Step 5: 全量提交**

```bash
git status --porcelain
git add -A
git commit -m "docs: enhancements iteration complete"  # 若此前任务已提交则无变更
```

- [ ] **Step 6: 推送并开 PR**

```bash
git push -u origin iteration-docs-enhancements
gh pr create --title "docs: screenshots, English locale, and API reference generation" --body "实现 docs/superpowers/plans/2026-08-02-docs-enhancements.md。
- 截图：真实运行的产品截图（模型库 / 三维审查 / Diff Viewer），嵌入中文与英文页面。
- 双语：VitePress locales（root=zh-CN 不变，新增 en），英文优先集 11 页（首页、快速开始、总体架构、贡献、API 入口），无占位页。
- API 自动生成：edit-service 参考页由 OpenAPI schema 生成，Go 端点清单由 mux 注册扫描生成；npm run gen:api / check:api + CI 漂移检测 job。
- Roadmap 与内部计划同步更新后续任务。"
```

Expected: PR 创建成功；CI（docs build、api-reference、viewer 四组）全绿。

---

## Self-Review（写后自查）

- **Spec 覆盖**：§9.1 双语（英文优先集完整、无占位、剩余页列为后续）、§9.2 API 自动生成（edit-service 页面生成 + Go 机器可读清单 + CI 漂移检测 + 人工指南保留）；§9.3 截图经用户确认**不做**（变更记录见文首）；BotRS 的 locales 镜像组织为参考（root + zh/en 镜像，URL 前缀 `/en/`）。
- **占位符扫描**：无 TODO/TBD；英文 11 页全部有完整内容。
- **确定性**：生成脚本无时间戳、稳定排序；`check:api` 以 git diff 判漂移。
- **类型一致性**：config 侧边栏 link 与 en 页面文件一一对应（en/guide/4、en/development/1、en/reference/4、en/project/1、en/index）；生成的 `edit-api-reference` 在 zh/en 侧边栏均挂 `/reference/edit-api-reference`；机器产物路径与脚本一致（`site/reference/edit-api-reference.md`、`site/public/go-rest-api.routes.json`）。
- **风险**：截图依赖本机四组件栈与浏览器，若 edit-service 或转换失败，截图任务降级为仅模型库/审查图并如实说明；CI 不依赖截图（图片已提交）。
