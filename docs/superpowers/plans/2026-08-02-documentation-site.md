# AI_IFC 文档站（VitePress + GitHub Pages）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立基于 VitePress 的公开文档站 `docs/site/`，迁移并校订 Viewer 公开内容，配置 PR 构建 + main 自动部署 GitHub Pages，并把 SimpleCADAPI 文档与内部资料移出公开站点。

**Architecture:** `docs/` 重组为 `site/`、`internal/`、`archive/simplecadapi/`、`superpowers/` 四类；站点内容全部按源文档事实校订重写（单一信息源）；GitHub Actions 在 PR 验证构建、push main 部署 Pages（`base=/AI_IFC/`）。

**Tech Stack:** VitePress 1.x、Node.js 22（CI）、npm + `docs/package-lock.json`、GitHub Actions（`configure-pages` / `upload-pages-artifact` / `deploy-pages`）。

**来源规范：** `docs/superpowers/specs/2026-08-02-documentation-site-design.md`（已确认，本计划唯一事实基线）。

---

## Global Constraints

- 工作分支 `iteration-docs-site`；每完成一个任务提交一次。
- 内容事实基线 = spec §8：Viewer 是活跃产品；edit-service 已落地；diff 为属性级；PG 可选、模型文件仍文件系统；Docker Compose 未完成不得宣称一键部署；AI 生成/MCP/认证/多用户未交付；OpenAPI 为仓库内静态文件；不硬编码测试数量、不出现个人本机路径、兄弟仓库路径、内部 N+ 编号叙事。
- 所有文档命令从 `docs/` 执行：`npm ci`、`npm run docs:dev`、`npm run docs:build`。
- 构建不得有 dead link：VitePress 默认把站内死链视为构建错误，不得全局关闭。
- 移动/归档任何文件后，必须 `rg` 全仓 Markdown 更新相对链接（README、NOTICE、viewer README、edit-service README、internal 文档）。
- 不新增 Docker Compose、不做双语 locale、不做 OpenAPI 自动生成；这些只作为 Roadmap/内部计划中的后续任务记录。
- 每任务验证命令必须给出预期输出；`docs:build` 成功 = 退出码 0 + `build complete`。

---

## Task 0: 分支与基线

**Files:**
- Modify: `.git`（创建分支，需提升权限）

- [ ] **Step 1: 确认工作区干净**

Run: `git status --porcelain`
Expected: 空输出。

- [ ] **Step 2: 创建迭代分支**

Run（需批准，.git 为只读挂载）:

````bash
git switch -c iteration-docs-site
````

Expected: `Switched to a new branch 'iteration-docs-site'`；`git branch --show-current` 输出该分支名。

- [ ] **Step 3: 记录工具版本基线**

Run: `node --version && npm --version`
Expected: node ≥ 22（本机 26.x）、npm 12.x，均可满足 VitePress 要求。

- [ ] **Step 4: Commit（无文件变更时可跳过）**

本任务不产生文件变更，无需提交。

---

## Task 1: VitePress 脚手架与站点配置

**Files:**
- Create: `docs/package.json`
- Create: `docs/.gitignore`
- Create: `docs/package-lock.json`（由 `npm install` 生成）
- Create: `docs/site/.vitepress/config.mts`
- Create: `docs/site/index.md`
- Create: `docs/site/public/ai-tools.openapi.json`（从 `docs/ai-tools.openapi.json` 复制，Task 8 再切移动）

- [ ] **Step 1: 创建 `docs/package.json`**

````json
{
  "name": "ai-ifc-docs",
  "private": true,
  "type": "module",
  "scripts": {
    "docs:dev": "vitepress dev site",
    "docs:build": "vitepress build site"
  },
  "devDependencies": {
    "vitepress": "^1.6.0"
  }
}
````

- [ ] **Step 2: 创建 `docs/.gitignore`**

````gitignore
node_modules/
.vitepress/cache/
.vitepress/dist/
````

- [ ] **Step 3: 生成锁文件并安装依赖**

Run（docs/ 目录）: `npm install`
Expected: 生成 `docs/package-lock.json`；`node_modules/.bin/vitepress --version` 输出 1.x。

- [ ] **Step 4: 创建 `docs/site/.vitepress/config.mts`**

````ts
// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 0702hjj
import { defineConfig } from 'vitepress'

export default defineConfig({
  lang: 'zh-CN',
  title: 'AI_IFC',
  description: '自托管、开源的 IFC 审查与编辑平台',
  base: '/AI_IFC/',
  cleanUrls: true,
  lastUpdated: true,

  head: [
    ['meta', { name: 'theme-color', content: '#3fb950' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/AI_IFC/favicon.svg' }],
  ],

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
})
````

- [ ] **Step 5: 创建 `docs/site/public/favicon.svg`**

````svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#3fb950"/>
  <text x="16" y="22" font-family="monospace" font-size="16" font-weight="bold" text-anchor="middle" fill="#0d1117">IFC</text>
</svg>
````

- [ ] **Step 6: 创建 `docs/site/index.md`（首页，FRP-Panel 式产品入口）**

````markdown
---
layout: home

hero:
  name: AI_IFC
  text: IFC 审查与编辑平台
  tagline: 自托管、开源。在浏览器里审查 IFC 模型、真实修改属性、做语义版本对比，并把同一套编辑 API 开放给人与 AI。
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/project-intro
    - theme: alt
      text: 上传第一个 IFC
      link: /guide/first-ifc

features:
  - title: 三维审查
    details: 上传 IFC 即转为 XKT 快速渲染；模型树、属性检查、剖切、测量与 3D Issue 钉一应俱全。
  - title: 真实编辑
    details: 属性 override 与 pending → commit 两阶段真改 IFC，每次 commit 生成不可变版本快照。
  - title: 语义版本对比
    details: 按 GlobalId 的属性级 diff：新增/删除/修改着色与 old → new 明细，不带几何噪声。
  - title: 人 / AI 双角色
    details: 人与 AI 共用同一套 REST 编辑 API，provenance 区分 UI / AI；OpenAPI 工具目录可直接喂给 LLM。
---

## 它能做什么

AI_IFC 是一个 IFC（Industry Foundation Classes）模型的审查与编辑平台，由四个组件构成：

- **web**：React + xeokit 浏览器端，负责模型库、三维查看、属性检查、Issue、属性编辑与版本对比。
- **server**：Go 后端，负责上传、转换队列、REST API 与编辑编排，存储可选文件或 PostgreSQL。
- **converter**：Node 转换器，把 IFC 转为 XKT 几何与语义元数据。
- **edit-service**：Python（FastAPI + IfcOpenShell）编辑服务，负责真改 IFC、版本快照与语义 diff。

典型工作流：上传 IFC → 转换完成后三维审查 → 对构件提 Issue → 编辑属性（override 或真改）→ commit 生成版本 → 用 Diff 对比版本变化。

## 开始路径

1. [项目介绍](/guide/project-intro) — 了解定位、能力边界与四组件架构。
2. [环境要求与本地部署](/guide/quickstart) — 装好依赖，用四个终端启动全部组件。
3. [上传第一个 IFC](/guide/first-ifc) — 上传样例模型，走一遍审查 → Issue → 编辑 → Diff 全流程。
4. [Viewer REST API](/reference/rest-api) 与 [IFC 编辑 API](/reference/edit-api) — 接口契约；[AI 接入](/reference/ai) 面向 AI agent。

## 项目状态

平台已端到端可用（上传 → 转换 → 审查 → 编辑 → commit → diff）。当前仓库以 `viewer/` 为活跃产品；仓库历史中的 SimpleCADAPI（SCAD）代码作为归档保留，详见 [License 与第三方组件](/project/license)。

版本路线见 [Roadmap](/project/roadmap)，已知边界见 [已知限制](/project/known-limits)。
````

- [ ] **Step 7: 复制 OpenAPI 静态产物到站点 public 目录**

Run: `cp ../ai-tools.openapi.json site/public/ai-tools.openapi.json`（docs/ 下执行）
Expected: `docs/site/public/ai-tools.openapi.json` 存在且与源文件一致（`cmp` 退出码 0）。

- [ ] **Step 8: 验证脚手架可构建**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，输出包含 `build complete`；`site/.vitepress/dist/index.html` 存在。

- [ ] **Step 9: Commit**

````bash
git add docs/package.json docs/package-lock.json docs/.gitignore docs/site/.vitepress/config.mts docs/site/index.md docs/site/public/favicon.svg docs/site/public/ai-tools.openapi.json
git commit -m "docs: add VitePress scaffold for public docs site"
````

---

## Task 2: GitHub Actions 文档构建与 Pages 部署

**Files:**
- Create: `.github/workflows/docs.yml`

- [ ] **Step 1: 创建 `.github/workflows/docs.yml`**

````yaml
name: docs

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    name: docs build (VitePress)
    runs-on: ubuntu-latest
    concurrency:
      group: docs-build-${{ github.ref }}
      cancel-in-progress: true
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
          cache-dependency-path: docs/package-lock.json
      - run: npm ci
        working-directory: docs
      - run: npm run docs:build
        working-directory: docs
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: docs/site/.vitepress/dist

  deploy:
    name: deploy to GitHub Pages
    if: github.event_name != 'pull_request'
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    concurrency:
      group: docs-pages-deploy
      cancel-in-progress: true
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
````

要点（对应 spec §4.2）：PR 只构建不部署；push main 与 `workflow_dispatch` 部署；部署独立 concurrency group `docs-pages-deploy`；使用官方三个 Pages actions；环境 `github-pages`。

- [ ] **Step 2: 校验 YAML 可解析**

Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/docs.yml')); print('yaml ok')"`
Expected: `yaml ok`（若无 pyyaml，用 `node -e "require('js-yaml')"` 不可用时改为人工核对缩进）。

- [ ] **Step 3: Commit**

````bash
git add .github/workflows/docs.yml
git commit -m "ci: build docs on PR and deploy Pages on main"
````

---

## Task 3: 快速开始分组（guide/）

**Files:**
- Create: `docs/site/guide/project-intro.md`
- Create: `docs/site/guide/quickstart.md`
- Create: `docs/site/guide/first-ifc.md`
- Create: `docs/site/guide/configuration.md`

- [ ] **Step 1: 创建 `docs/site/guide/project-intro.md`**

````markdown
# 项目介绍

AI_IFC 是一个**自托管、开源**的 IFC 模型审查与编辑平台。它从 SimpleCADAPI fork 而来，但活跃产品是 `viewer/` 下的 IFC 平台；SimpleCADAPI 相关代码作为归档保留，详见 [License 与第三方组件](/project/license)。

## 定位

- **是什么**：IFC 模型的自托管审查 + 编辑平台——真改 IFC 属性、语义化版本对比，以及人/AI 双角色共用的编辑 API。
- **面向谁**：内网/个人自托管的 BIM 团队；做 IFC 工具链的开发者；需要「AI 可接入的 BIM 编辑底座」的研究者。
- **当前能力**：端到端可用——上传 → 转换 → 三维审查 → Issue → 属性编辑 → commit → 版本 diff。

## 能力边界

**已交付：**

- IFC 上传与队列化转换（XKT 几何 + 语义元数据）。
- 三维审查：模型树、属性检查、可见性工具、剖切、测量、NavCube。
- Issue 与 3D Pin：带相机视角与截图创建、状态流转、点击定位。
- 属性编辑：白名单字段 override（显示层）与 pending → commit 两阶段真改 IFC。
- 版本快照与属性级语义 diff（Diff Viewer）。
- 人与 AI 共用同一套编辑 API，provenance 区分 `UI` / `AI`。
- PostgreSQL 可选存储（issues / overrides / change log）；不配置时文件存储零依赖可跑。

**未交付（见 [已知限制](/project/known-limits) 与 [Roadmap](/project/roadmap)）：**

- 多用户/鉴权；AI 生成 IFC 本体；MCP 封装；几何 diff；Docker Compose 一键部署；完整中英文双语站点；OpenAPI 自动生成。

## 四组件架构

| 组件 | 技术 | 职责 |
| --- | --- | --- |
| `web` | React 19 + xeokit | 模型库、三维查看、属性编辑、Issue、Diff Viewer |
| `server` | Go 1.26（stdlib + pgx/v5） | 上传/转换队列、REST API、编辑编排、存储抽象 |
| `converter` | Node CLI（web-ifc + xeokit-convert） | IFC → XKT + metadata.json |
| `edit-service` | Python FastAPI + IfcOpenShell + ifcdiff | 真改 IFC、pending/commit、版本快照、语义 diff |

三语言并存是生态现实而非设计偏好：每个语言绑定的是该生态里唯一或最优的 IFC 库。服务之间通过 REST 与子进程解耦，任一组件可独立替换。

详细架构见 [总体架构](/development/architecture)。
````

- [ ] **Step 2: 创建 `docs/site/guide/quickstart.md`**

````markdown
# 环境要求与本地部署

## 环境依赖

| 依赖 | 版本 | 用途 | 必需性 |
| --- | --- | --- | --- |
| Go | 1.26+ | server | 必需 |
| Node.js | 18+ | converter（`npm install` 一次即可，无需常驻） | 必需 |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | 编辑/diff 功能必需；纯浏览可不要 |
| PostgreSQL | 14+ | issues/changes/overrides 持久化 | 可选（默认文件存储） |
| IfcOpenShell 源码 checkout | v0.8 | ifcdiff 的本地 editable 依赖 | 当前必需（见下方说明） |

> **ifcdiff 依赖说明**：edit-service 的 `pyproject.toml` 目前以本地 editable 路径引用同级目录的 IfcOpenShell 源码（`src/ifcdiff`）。即运行 edit-service 前，需要在仓库同级目录准备一份 IfcOpenShell v0.8 checkout。这是已记录的部署限制，自包含处理（vendor 或 git source）在 Roadmap 中。

## 启动（四个终端）

```bash
# 0. 一次性：安装依赖
cd converter && npm install
cd ../web && npm install
cd ../edit-service && uv sync

# 1. edit-service（:8100）—— VIEWER_DATA_DIR 必须指向 data 的绝对路径
cd services/ifc
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server（:8090）
cd server && go run ./cmd/server

# 3. web（:5173）
cd web && npm run dev
```

打开 http://localhost:5173 即可使用。完整配置项见 [配置说明](/guide/configuration)。

## 验证

```bash
# 端到端冒烟（需 server 运行；edit-flow 段在 edit-service 不可达时自动跳过）
cd viewer && ./scripts/smoke.sh

# 各层测试
cd server && go test ./...
cd services/ifc && uv run pytest
cd web && npm test
cd converter && npm test
```

> 注意：上传、转换、审查等浏览功能不依赖 edit-service 与 PostgreSQL；编辑、版本、diff 需要 edit-service 运行。
````

- [ ] **Step 3: 创建 `docs/site/guide/first-ifc.md`**

````markdown
# 上传第一个 IFC

仓库自带一个 buildingSMART 官方样例 IFC：

`converter/test/fixtures/wall-with-opening-and-window.ifc`

## 操作流程

1. **上传**：在模型库页拖入 `.ifc` 文件（≤200MB，非 .ifc 会被拒绝）。上传后状态进入 `converting`，页面以 2 秒间隔轮询，完成后变为 `ready`；失败会显示错误并可重试。
2. **进入模型**：点击模型进入三维查看器。左侧模型树默认展开一层，可搜索、按 IFC 类型过滤、逐节点显隐；点击构件会高亮并在右侧属性面板显示其属性集（pset）。
3. **审查**：使用可见性工具栏（隐藏/隔离/X-Ray/重置）、剖切滑杆与距离测量检查模型；选中构件可创建 Issue（自动携带相机视角与截图），3D 钉会出现在构件上。
4. **编辑**：在属性面板中，白名单字段（Name/Description/Classification/FireRating/Comments）可直接行内编辑保存为 override；详细编辑流程见 [IFC 属性编辑](/viewer/editing)。
5. **对比版本**：工具栏「Diff」选择 base 与 target（版本或 current）进行语义对比，见 [版本与 Diff Viewer](/viewer/versions-diff)。

## 排查

| 现象 | 处理 |
| --- | --- |
| 上传后一直 converting | 查看 server 日志中的 converter stderr；手动运行 `node converter/convert.js <ifc> <outDir>` 复现；确认 `nodeBin` / `converterScript` 配置 |
| 转换 failed | `POST /api/models/{id}/retry` 重试 |
| 编辑报 404 model not found | edit-service 的 `VIEWER_DATA_DIR` 与 Go `dataDir` 不是同一目录 |
| 编辑报 422 | 属性名不存在或值类型不符——请求零副作用，修正后重发 |
| commit 报 409 | 没有 pending（pending 存内存，edit-service 重启会丢） |
| 改了属性前端没刷新 | 经 Go 代理 commit 才触发重转；直连 edit-service 后需手动刷新或经代理重放 |

完整排查表见 [测试与调试](/development/testing)。
````

- [ ] **Step 4: 创建 `docs/site/guide/configuration.md`**

````markdown
# 配置说明

## Go server（`server/server_config.json`）

路径相对于进程工作目录解析（非可执行文件目录）。

| key | 默认 | env 覆盖 | 说明 |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | 监听地址 |
| `dataDir` | `../data` | — | 数据目录（**与 edit-service 的 VIEWER_DATA_DIR 同目录**） |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | 转换器调用 |
| `maxUploadMB` | `200` | — | 上传上限 |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | 配置即启用 PostgreSQL（自动建表），空则文件存储 |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service 地址 |

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

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 数据目录（相对进程工作目录）；**必须与 server `dataDir` 指向同一目录**，否则编辑请求 404 |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |

## PostgreSQL（可选）

- 不配置 `pgDSN` / `VIEWER_PG_DSN` 时，issues / overrides / change log 全部使用文件存储，零外部依赖可跑。
- 配置后 server 启动时自动创建 `issues` / `changes` / `overrides` 表；模型文件（uploads / models / 版本快照）始终在文件系统。
- 测试时需 `VIEWER_TEST_PG_DSN` 指向**专用测试库**（测试会 DROP 表）。

## 端口

默认端口：server `8090`、edit-service `8100`、web 开发服务器 `5173`。
````

- [ ] **Step 5: 验证构建**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`，无 dead link 报错。

- [ ] **Step 6: Commit**

````bash
git add docs/site/guide
git commit -m "docs: add quickstart section (intro, deploy, first IFC, configuration)"
````

---

## Task 4: Viewer 使用分组（viewer/）

**Files:**
- Create: `docs/site/viewer/library.md`
- Create: `docs/site/viewer/model-tree.md`
- Create: `docs/site/viewer/viewing.md`
- Create: `docs/site/viewer/issues.md`
- Create: `docs/site/viewer/editing.md`
- Create: `docs/site/viewer/versions-diff.md`

- [ ] **Step 1: 创建 `docs/site/viewer/library.md`**

````markdown
# 模型库与模型上传

模型库页是平台的入口：上传、列表、状态跟踪、重试、下载与删除。

## 上传

- 拖入或选择 `.ifc` 文件（≤200MB）；非 `.ifc` 扩展名与超限文件会被前端拦截，后端同样校验。
- 上传后模型进入 `converting` 状态，server 排队调用 converter 生成 XKT 与元数据；页面以 2 秒间隔轮询直到所有模型脱离 `converting`。
- 状态取值：`converting`（转换中）、`ready`（可用）、`failed`（转换失败，可重试）。

## 列表操作

- **重试**：`failed` 模型可重新入队转换。
- **下载**：下载原始 IFC 文件（未修改的上传版本）。
- **删除**：级联删除 IFC、XKT、元数据、状态文件以及该模型的 issues / changes / overrides。

## 相关 API

上传、列表、重试、下载、删除的接口契约见 [Viewer REST API](/reference/rest-api)。
````

- [ ] **Step 2: 创建 `docs/site/viewer/model-tree.md`**

````markdown
# 模型树与属性检查

## 模型树

左侧面板展示按空间结构组织的模型树（Site → Building → Storey → 构件），基于 converter 导出的元数据构建：

- **搜索**：按名称或类型过滤。
- **类型过滤**：按 IFC 类型（如 IfcWall）过滤构件。
- **显隐**：逐节点切换可见性。
- **定位**：点击节点，相机飞行到构件并高亮选中。

## 属性检查器

右侧属性面板显示选中构件的属性集（pset）：

- pset 分组折叠，默认展开第一个。
- 属性搜索与复制（写入剪贴板）。
- 白名单字段（Name / Description / Classification / FireRating / Comments）可行内编辑，保存为 override 并带修改标记，见 [IFC 属性编辑](/viewer/editing)。

## 技术说明

元数据由 converter 以 xeokit 标准元模型 JSON 导出，`metaObjects[].id` 为 IFC GlobalId，与 XKT 实体 id 一致，因此选中、着色、diff 结果全部对齐。Schema 见 [Viewer REST API](/reference/rest-api) 的 metadata.json 一节。
````

- [ ] **Step 3: 创建 `docs/site/viewer/viewing.md`**

````markdown
# 可见性、剖切与测量

## 可见性工具栏

- **隐藏选中**：隐藏当前选中构件。
- **隔离**：只显示选中构件。
- **X-Ray**：半透明显示全部构件。
- **重置可见性**：恢复全部构件可见。

## 剖切

通过 X / Y / Z 三个方向的滑杆移动剖切面，用于观察模型内部结构。

## 测量

距离测量：依次点击两点，显示两点间距；双击结束测量，可清除。

## 其他视图工具

- **NavCube**：方向指示与视图切换。
- **复位视角**：恢复默认相机位置。
- 轨道旋转 / 缩放 / 平移为 xeokit 默认交互。
````

- [ ] **Step 4: 创建 `docs/site/viewer/issues.md`**

````markdown
# Issue 与 3D Pin

## 创建 Issue

1. 选中构件。
2. 在底部 Issue 面板点「新建 Issue」，填写标题（必填）与评论。
3. 创建时自动携带当前相机视角与画布截图；Issue 出现在列表中，3D 钉覆盖在构件上。

## 状态流转

`open` → `checking` → `resolved`，可在列表中切换。Issue id 格式 `i_` + 12 位小写 hex。

## 3D Pin

- 每个带 entityId 的 Issue 对应一个 HTML 钉，实时投影到构件位置；构件不可见或钉在屏幕外时自动隐藏。
- 点击钉或列表条目：恢复创建时的相机视角、选中构件并高亮该 Issue。

## 修改历史

底部面板提供「Issues / 修改历史」双 tab。修改历史展示 change log（时间、实体、字段、old → new、author），按时间倒序，保存属性后自动刷新。

## 接口契约

Issue CRUD 与截图静态服务见 [Viewer REST API](/reference/rest-api)。
````

- [ ] **Step 5: 创建 `docs/site/viewer/editing.md`**

````markdown
# IFC 属性编辑

属性编辑分两阶段：**override（显示层）→ 真改（写回 IFC）**。

## 第一阶段：属性 override

属性面板中白名单字段可编辑，白名单恰好为：

`Name`、`Description`、`Classification`、`FireRating`、`Comments`

- 编辑保存后作为 override 覆盖显示值，**不修改 IFC 本体**，被覆盖字段带修改标记。
- 空字符串 = 清除该字段的 override。
- 每次修改逐字段写入一条 change log（`operation=update`，`author=local-user`，`provenance={source:"UI"}`），可在修改历史 tab 查看。
- 相关 API：`GET /api/models/{id}/overrides`、`PUT /api/models/{id}/entities/{entityId}/properties`、`GET /api/models/{id}/changes`。

## 第二阶段：override 迁移为真改

`POST /api/models/{id}/overrides/migrate` 把当前全部 override 回放为真实 IFC 修改：

- 每个实体先 PUT pending，再一次性 commit（`operation=migrate`），生成新的版本快照。
- 成功字段清除 override；失败字段保留 override，并在响应 `failed` 中带原因。
- 有任何成功即触发 XKT 重转。

## 真改编辑流（pending → commit）

真改编辑是两阶段事务：

1. **PUT pending**：把 `fields`（直接属性）与 `psets`（属性集，不存在则创建）应用到内存模型并记为 pending；**不落盘**。先全量校验再应用——任一校验失败则零副作用。
2. **POST commit**：全部 pending 原子落盘（tmp + rename，持每模型锁）→ 生成版本快照 → 追加编辑历史 → 清空 pending。

经浏览器（Go 代理）commit 时，Go server 还会：把 entries 展开写入 change log、用 IfcDiff 补充 diff 字段、把模型置为 `converting` 并排队重转 XKT——完成后前端自动重载。

要点：

- pending 只存内存，edit-service 重启即丢失未 commit 的修改；history 与版本快照不受影响。
- 重复 commit（无 pending）返回 409。
- 多请求并发由每模型一把锁串行化。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
````

- [ ] **Step 6: 创建 `docs/site/viewer/versions-diff.md`**

````markdown
# 版本与 Diff Viewer

## 版本快照

每次 commit 生成一个不可变版本快照，只增不改、原子写：

- 首次 commit：先把原始上传文件快照为 `v1`，落盘后再快照新文件为 `v2`。
- 之后每次 commit 成功产生 `v{n+1}`。
- 快照存放于 `{dataDir}/models/{id}/versions/v{n}.ifc`。

## Diff 面板

工具栏「Diff」打开对比面板：

1. 选择 base（v1 / v2 / …）与 target（版本或 `current`）。
2. 点击「对比」：**绿 = 新增、黄 = 修改、红 = 删除**。
3. 点击条目定位构件；修改条目可展开查看字段级 old → new。
4. 「清除」复位着色。

## Diff 语义

- 以 **GlobalId** 为实体标识：`added` / `removed` 为 guid 列表；`changed` 为实体直接属性与 pset 属性的字段级 old → new。
- 基于 ifcdiff，仅以 `attributes` / `property` 两种 relationship 运行；entity 引用属性（ObjectPlacement、Representation 等几何表示层）不参与比较，**当前不提供几何 diff**。
- 删除构件在当前 XKT 中已无几何，只进入红色列表（设计决策）。
- base/target 均为不可变版本时，结果缓存在 `versions/diff-{base}-{target}.json`；`target="current"` 不缓存。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
````

- [ ] **Step 7: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`。

```bash
git add docs/site/viewer
git commit -m "docs: add viewer usage section (library, tree, viewing, issues, editing, diff)"
```

---

## Task 5: 开发指南分组（development/）

**Files:**
- Create: `docs/site/development/architecture.md`
- Create: `docs/site/development/repo-structure.md`
- Create: `docs/site/development/web.md`
- Create: `docs/site/development/server.md`
- Create: `docs/site/development/converter.md`
- Create: `docs/site/development/edit-service.md`
- Create: `docs/site/development/testing.md`

- [ ] **Step 1: 创建 `docs/site/development/architecture.md`**

````markdown
# 总体架构

```mermaid
graph LR
  subgraph 客户端层
    UI[浏览器<br/>React 19 + xeokit<br/>web]
    AI[AI Agent]
  end

  subgraph 服务层
    GO[Go server :8090<br/>server<br/>编排 / REST / 存储抽象]
    PY[Python edit-service :8100<br/>services/ifc<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>converter<br/>IFC → XKT + metadata.json]
  end

  subgraph 存储层
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(文件系统<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|同一套编辑 API| PY
  AI -->|或经 Go 代理| GO
  GO -->|/api/models/{id}/edit/* 代理 + 编排| PY
  GO -->|子进程 node convert.js| CV
  GO -->|pgx/v5，可选| PG
  GO --> FS
  PY -->|真改 IFC / 版本快照 / history| FS
  CV -->|model.xkt + metadata.json| FS
```

## 组件职责

| 组件 | 技术 | 职责 | 选型原因 |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | 审查/编辑/Diff 的全部交互 | xeokit 的 XKT 二进制加载与 BIM 工具链 |
| server | Go 1.26（stdlib net/http + pgx/v5） | 上传/转换队列、REST、编辑编排、存储抽象 | 静态编译、并发模型 |
| converter | Node CLI（web-ifc + xeokit-convert） | IFC → XKT 几何 + 语义提取 | xeokit-convert 只有 npm 形态 |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | 真改 IFC、pending/commit、版本快照、语义 diff | IfcOpenShell 是 IFC 编辑的事实标准 |
| PostgreSQL | 可选 | issues / changes / overrides 三表 | 不配置 `pgDSN` 时全部落文件，零依赖可跑 |

## 核心数据流

### 上传转换流

```
浏览器上传 .ifc → Go 校验/存 uploads/{id}.ifc（status=converting）
  → 转换队列（2 worker，dedup + dirty 重跑）→ node convert.js
  → models/{id}/model.xkt（几何）+ metadata.json（空间树/pset）
  → status=ready → 前端 XKTLoaderPlugin 同时加载几何与语义
```

关键不变量：**XKT 构件 id = metadata metaObject id = IFC GlobalId**——选中、着色、diff 结果全靠这条链对齐。

### 编辑流

```
PUT /models/{id}/entities/{guid}  {fields, psets, author, provenance}
  → 全量校验（任一不合法 → 422 零副作用）→ 应用到内存模型 → 记 pending（含 IFC 真原值 oldValue）
POST /models/{id}/commit
  → 原子写盘（tmp+rename，持每模型锁）→ 版本快照 versions/v{n+1}.ifc → 追加 edit-history.json → 清 pending
（经 Go 代理时，编排继续：）
  → change log 按字段展开（operation=update，diff 由 IfcDiff 补充，非致命）
  → 转换队列重转 XKT → 前端轮询到 ready 自动重载
```

### 版本与 diff 流

- 首次 commit 前把原始上传复制为 `versions/v1.ifc`；每次 commit 快照 `v{n+1}.ifc`（只增不改）。
- `POST /models/{id}/diff {base, target}`：IfcDiff（`relationships=["attributes","property"]`，从构造上排除几何）给出 added/removed 集合；适配层对 changed 实体自算字段级 old/new；归约为 `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`。
- 快照间 diff 结果缓存（版本不可变，缓存天然有效）。

### override → 真改迁移流

```
读全部 override → 逐 entity 映射（Name/Description/Comments → fields；
  FireRating → 从 metadata.json 反查 pset；Classification → 试 fields，422 则进 failed）
→ 每 entity 一次 PUT（pending）→ 全部一次 commit（operation=migrate）
→ 成功字段清 override；change log 带真原值；失败字段保留 override 并带原因
→ 有任何成功 → 重转
```

## commit / 版本模型

change log 条目含：`author`（默认 `local-user`，v1 无认证）、`createdAt`（UTC）、`operation`（`update | migrate`）、`diff`（commit 时 IfcDiff 补充）、`provenance`（`{source: UI|AI}`，API 层枚举校验）。版本为线性快照序列（分支/合并未做，属多用户范围）。

已知技术债（详见 [已知限制](/project/known-limits)）：三份历史记录并存（Go change log / edit-service edit-history / 内存 pending）粒度与用途不同；ifcdiff 为本地 editable 依赖；pending 为内存态；diff 无超时控制；Python 侧存储仅文件模式。
````

- [ ] **Step 2: 创建 `docs/site/development/repo-structure.md`**

````markdown
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
│   ├── archive/simplecadapi/  # 原 SCAD API/core/stdlib/legacy 文档（不发布）
│   └── superpowers/           # 设计规范与实施计划
├── research/                  # 调研笔记与目标映射（内部）
├── src/simplecadapi/          # 归档：SimpleCADAPI（SCAD → STEP），仓库起点
├── skills/simplecadapi/       # 归档：SimpleCADAPI skill 包
├── examples/                  # 归档：SCAD 示例
├── .github/workflows/         # CI（viewer）与 docs（构建 + Pages 部署）
├── LICENSE                    # AGPL-3.0-only
└── NOTICE                     # 三方组件与归档代码边界
```

## 文档边界

- `docs/site/` 是唯一公开文档站源，内容由 VitePress 构建并以 `/AI_IFC/` 为 base 发布到 GitHub Pages。
- `docs/internal/` 与 `docs/archive/simplecadapi/` 不进入站点导航与搜索。
- 各服务 README 只保留邻近源码的最小启动提示，详细说明一律链接到公开文档站。
````

- [ ] **Step 3: 创建 `docs/site/development/web.md`**

````markdown
# Web 前端

`web/`：React 19 + TypeScript + Vite + zustand + xeokit-sdk，开发端口 `:5173`。

## 命令

```bash
cd web
npm install
npm run dev        # 开发服务器，/api 与 /models 代理到 :8090
npm test           # vitest 单测
npm run build      # tsc -b + vite build（类型检查）
npm run lint       # oxlint
```

## 目录与组件树

```
src/
├── App.tsx                 路由：/ → LibraryPage，/view/:id → ViewerPage
├── api/client.ts           request<T> 解包 {code,message,data}；全部 API 函数
├── pages/LibraryPage.tsx   上传（拖拽 .ifc ≤200MB）、状态轮询、重试/删除/下载
├── pages/ViewerPage.tsx    ViewerProvider + Toolbar + 各面板；模型状态轮询
└── viewer/
    ├── ViewerContext.tsx   xeokit Viewer + XKTLoaderPlugin（xkt + metadata 双加载）
    ├── ModelTreePanel.tsx  空间树（搜索/类型过滤/显隐，默认展开 1 层）
    ├── PropertyPanel.tsx   pset 展示 + 白名单字段行内编辑（override）
    ├── IssuePanel.tsx      Issues / 修改历史双 tab；新建 Issue（相机 + 截图）
    ├── IssuePins.tsx       3D HTML 钉 overlay（每帧投影同步，点击定位）
    ├── DiffPanel.tsx       版本选择 → diff 着色 + old→new 列表 + 点击定位
    ├── Toolbar.tsx         复位视角/剖切/测量/Diff/可见性/下载
    ├── VisibilityToolbar.tsx / SectionControl.tsx / useMeasurements.ts
    ├── usePicking.ts       拾取 + 选中高亮
    ├── overrides.ts        EDITABLE_FIELDS 白名单 + applyOverrides 渲染合并
    └── store.ts            zustand：selectedId/tool/hiddenIds/overrides/... 
```

## 关键机制

- **选中链路**：`setSelected(id)` → usePicking 高亮 → PropertyPanel 显示该 GlobalId 的 pset。
- **override 显示**：渲染时 `applyOverrides` 把 override 值覆盖在原值上并带修改标记；保存走 `PUT /api/models/{id}/entities/{entityId}/properties`。
- **Diff 着色**：diff 返回的 guid 即 scene object id；`entity.colorize` 设置颜色，清除时置 null；removed 构件在当前 XKT 无几何，仅列表呈现。
- **自动刷新**：ViewerPage 持续轮询模型状态，`converting → ready` 转换时 remount ViewerProvider 重载 XKT（外部 commit / AI 直改触发的重转也能捕获）。
````

- [ ] **Step 4: 创建 `docs/site/development/server.md`**

````markdown
# Go Server

`server/`：Go 1.26（stdlib net/http + pgx/v5 唯一第三方依赖），默认 `:8090`。

## 命令

```bash
cd server
go run ./cmd/server          # 默认读取 ./server_config.json
go test ./...                # 单元 + httptest + 并发（-race 下通过）
go vet ./...
```

## 包结构

```
cmd/server/main.go        config（json + VIEWER_PG_DSN / VIEWER_EDIT_SERVICE_URL env）+ 依赖装配
internal/
├── api/                  全部 handler（api.go 核心 + edit.go 编辑编排），envelope {code,message,data}
├── store/                模型元数据/文件存储：Create/Get/List/SetStatus/Delete/Recover
├── convert/              转换队列：Runner 接口、Queue（2 worker、dedup、dirty 重跑、重启 Recover）
├── issue/ change/ override/   各 Store 接口 + FileStore + PgStore（构造时自动建表）
└── editsvc/              edit-service HTTP 客户端（简单调用 10s / commit·diff 120s）
```

## 端点全表

| 路由 | 说明 |
| --- | --- |
| `POST /api/models` | 上传（multipart `file`，.ifc，限大小）→ 入转换队列 |
| `GET /api/models` / `GET /api/models/{id}` | 列表（createdAt 倒序）/ 详情 |
| `POST /api/models/{id}/retry` | failed 重转 |
| `DELETE /api/models/{id}` | 级联删 issues/changes/overrides + 文件 |
| `GET /api/models/{id}/download` | 下载原 IFC |
| `GET /models/{id}/model.xkt` · `/metadata.json` | 静态产物（无 envelope） |
| `GET/POST /api/models/{id}/issues` · `PATCH/DELETE .../issues/{issueId}` | Issue CRUD（截图 ≤5MB） |
| `GET /models/{id}/issues/{file}` | Issue 截图（文件名白名单正则） |
| `GET /api/models/{id}/changes` | 修改记录（change log） |
| `GET /api/models/{id}/overrides` | `map[entityId]map[field]value` |
| `PUT /api/models/{id}/entities/{entityId}/properties` | override 写入（白名单五字段；每字段一条 change） |
| `POST /api/models/{id}/overrides/migrate` | override → 真改迁移 |
| `PUT /api/models/{id}/edit/entities/{guid}` | 代理至 edit-service（provenance 先校验） |
| `GET/DELETE /api/models/{id}/edit/pending` · `GET .../edit/history` · `GET .../edit/versions` · `POST .../edit/diff` | 代理透传 |
| `POST /api/models/{id}/edit/commit` | 编排：Python commit → change log 展开 → 重转；change log 失败降级 `warning` |

错误映射（代理）：Python 404 → 404 / 409 → 409 / 422 → 400 / 其他 → 502。模型 id 校验 `^m_[0-9a-f]{16}$`（路径穿越防护，与 Python 侧同规则）。

## 存储双实现

- 三个领域 store（issue/change/override）各有 `Store` 接口 + FileStore（`models/{id}/*.json`，tmp+rename 原子写）+ PgStore（pgx/v5，构造时建表）。
- 切换：`server_config.json` 的 `pgDSN` 或 env `VIEWER_PG_DSN`；不配置即 File 模式。
- 模型文件本身始终文件存储。
````

- [ ] **Step 5: 创建 `docs/site/development/converter.md`**

````markdown
# IFC Converter

`converter/`：Node CLI，基于 web-ifc + xeokit-convert，把 IFC 转为 XKT 几何与语义元数据，由 server 以子进程方式调用，无需常驻。

## 用法

```bash
node convert.js <input.ifc> <outDir>
```

产出：

- `model.xkt`：二进制几何。
- `metadata.json`：xeokit 标准元模型（空间结构树 + 属性集）。

成功时 stdout 末行输出 `{"ok":true,...}`；参数缺失退出码 2，转换失败退出码 1（stderr 报错）。

## 语义提取

- `lib/metadata.js` 用 web-ifc 遍历空间结构；`metaObject id = IFC GlobalId`（fallback `e<expressID>`）；pset 合成 id `pset_<expressID>_<n>`。
- convert.js 内置校验：XKT 实体 id 与 metaModel id 必须一致，不一致直接报错退出。
- 重转触发：上传、retry、commit 编排、override 迁移（经 Go 队列；对运行中的同 id 任务做 dirty 重跑，保证最新内容最终被转换）。

## 测试

```bash
cd converter
npm install
npm test    # node:test 集成测试：真实 IFC 样例（buildingSMART 官方 fixture）转换快照
```
````

- [ ] **Step 6: 创建 `docs/site/development/edit-service.md`**

````markdown
# Edit Service

`services/ifc/`：Python FastAPI + ifcopenshell + ifcdiff，默认 `:8100`，提供真改 IFC、pending/commit、版本快照与语义 diff。

## 运行与配置

```bash
cd services/ifc
uv sync
uv run uvicorn app.main:app --port 8100
```

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 与 Go `dataDir` 同目录（必须） |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |

> ifcdiff 当前以本地 editable 路径依赖 `../../../IfcOpenShell/src/ifcdiff`（deepdiff/orderly-set 随它进入）；自包含处理见 [Roadmap](/project/roadmap)。

## 编辑 API

模型 id 匹配 `^m_[0-9a-f]{16}$`，对应 IFC 路径 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

| 端点 | 语义 |
| --- | --- |
| `PUT /models/{id}/entities/{guid}` | 应用 `fields`/`psets` 到内存模型并记为 pending（不落盘）；先全量校验再应用（原子） |
| `GET /models/{id}/pending` | 列出当前 pending |
| `DELETE /models/{id}/pending` | 丢弃 pending：卸载并重载内存模型 |
| `POST /models/{id}/commit` | 全部 pending 原子落盘 → 版本快照 → 追加 history → 清空 pending；无 pending → 409 |
| `GET /models/{id}/history` | 列出持久化编辑历史（含真实 oldValue） |
| `GET /models/{id}/versions` | 版本快照列表与 current |
| `POST /models/{id}/diff` | 版本间语义 diff（base/target，target 可为 `current`） |

完整契约（body、错误码、Go 代理映射）见 [IFC 编辑 API](/reference/edit-api)。

## 实现要点

- `app/registry.py`：模型缓存（同路径同对象）/ 原子保存（tmp + os.replace）/ 每路径文件锁。
- `app/versions.py`：版本只增不改；首次 commit 先存 v1（原上传）再存 v2。
- `app/diffing.py`：IfcDiff 适配——仅 `attributes`/`property` 两种 relationship；changed 用 `get_info()`+`get_psets()` 自算字段级 old/new；快照间结果缓存。
- history 持久化在 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`（原子写）。

## 测试

```bash
cd services/ifc
uv run pytest
```
````

- [ ] **Step 7: 创建 `docs/site/development/testing.md`**

````markdown
# 测试与调试

## 各模块测试

| 模块 | 框架 | 覆盖范围 | 运行命令 |
| --- | --- | --- | --- |
| converter | node:test | 真实 IFC 转换集成（快照、引用完整性、id 一致性） | `cd converter && npm test` |
| server | go test | 单元 + httptest API + 并发（`-race`） | `cd server && go test ./... && go vet ./...` |
| edit-service | pytest | 编辑 / 版本 / diff 路由 | `cd services/ifc && uv run pytest` |
| web | vitest + jsdom | api client / 组件 / store / hook / 纯函数 | `cd web && npm test` |
| 端到端 | bash smoke | 上传→转换→下载→Issue→override/changes 全链路 | `cd viewer && ./scripts/smoke.sh`（需 server 运行） |

开发过程采用 TDD：每个模块先写失败测试再实现，测试文件与源码同目录。

## 端到端冒烟

前提：server 已在 `:8090` 运行；edit-service 可达时追加编辑链路（不可达自动跳过）。

```bash
cd server && go run ./cmd/server &
cd viewer && ./scripts/smoke.sh    # 成功以 smoke OK 结尾
```

覆盖：上传 fixture IFC → 轮询至 ready → XKT/metadata/download 200 → Issue 创建/列表/截图/状态流转/删除 → override 写入与生效值断言 → change log old→new 断言 → 清理。

## 手工验证清单（浏览器）

1. 打开 http://localhost:5173 ，上传 `.ifc`（≤200MB）。
2. 列表状态 `converting → ready`（2s 轮询）；failed 显示错误并可重试。
3. 进入查看器：模型渲染、轨道旋转/缩放、NavCube 可用。
4. 模型树：默认展开 1 层；搜索/类型过滤；节点显隐；点击节点相机飞行 + 高亮。
5. 属性面板：pset 折叠/搜索/复制；白名单字段行内编辑，override 生效并带标记。
6. 可见性工具栏：隐藏选中、隔离、X-Ray、重置。
7. 剖切（X/Y/Z 滑杆）与距离测量。
8. Issue：选中构件新建（自动截图与相机）→ 3D 钉显示并可点击定位 → 状态流转 → 删除。
9. Diff：选择 base/target → 绿/红/黄着色 + old→new 列表 → 清除复位。

## 故障排查

| 现象 | 排查 |
| --- | --- |
| 上传后一直 converting | 看 server 日志 converter stderr；手动跑 convert.js 复现；确认 nodeBin/converterScript |
| 转换 failed | `POST /api/models/{id}/retry` 重试 |
| 编辑 404 model not found | VIEWER_DATA_DIR 与 dataDir 不同目录 |
| 编辑 422 | 属性名/类型不符，请求零副作用，修正重发 |
| commit 409 | 无 pending（内存态，服务重启会丢） |
| 改了属性前端没刷新 | 直连 edit-service 的 commit 不触发重转；走 Go 代理 |
| PG 连不上 | 清空 pgDSN 回退文件存储 |
````

- [ ] **Step 8: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`。

```bash
git add docs/site/development
git commit -m "docs: add development guide (architecture, structure, four components, testing)"
```

---

## Task 6: API 与 AI 分组（reference/）

**Files:**
- Create: `docs/site/reference/rest-api.md`
- Create: `docs/site/reference/edit-api.md`
- Create: `docs/site/reference/ai.md`
- Create: `docs/site/reference/openapi.md`

- [ ] **Step 1: 创建 `docs/site/reference/rest-api.md`**

````markdown
# Viewer REST API

后端 base：`http://localhost:8090`；JSON 信封统一为 `{code, message, data}`，`code=0` 表示成功。模型 id 格式 `m_` + 16 位小写 hex。

## 模型

### POST /api/models

上传 IFC 文件并触发异步转换。请求：`multipart/form-data`，字段 `file`（仅 `.ifc`，≤200MB）。

响应：

```json
{"code":0,"message":"ok","data":{"id":"m_01J...","name":"Building-Architecture.ifc","status":"converting"}}
```

错误：`40001` 非法文件类型；`40002` 超出大小上限。

### GET /api/models

模型列表（前端 2s 轮询直至所有模型脱离 `converting`）：

```json
{"code":0,"message":"ok","data":[
  {"id":"m_01J...","name":"a.ifc","size":1832140,"status":"ready","createdAt":"2026-07-27T10:00:00Z","error":""}
]}
```

`status` ∈ `converting | ready | failed`。

### GET /api/models/{id}

单模型详情，结构同上。

### POST /api/models/{id}/retry

对 `failed` 模型重新入队转换；返回更新后的模型对象（`status:"converting"`）。

### DELETE /api/models/{id}

删除该模型的 IFC、XKT、metadata、状态文件及 issues/changes/overrides。响应 `data: null`。

### GET /api/models/{id}/download

下载原始 IFC，带 `Content-Disposition: attachment; filename="<name>"`。

## Issues

issue id 格式 `i_` + 12 位小写 hex；status ∈ `open | checking | resolved`；`author` 默认 `local-user`；`provenance.source` 默认 `UI`（创建时可显式覆盖）。

### GET /api/models/{id}/issues

返回 `data: Issue[]`，按 createdAt 降序。

### POST /api/models/{id}/issues

`multipart/form-data`：

- `issue`（必填）：JSON 字符串 `{"entityId","entityName","entityType","title","comment","author"?,"provenance"?,"camera":{"eye":[...],"look":[...],"up":[...]}}`，title 必填。
- `screenshot`（可选）：PNG 文件，≤5MB。

返回 `data: Issue`（含生成的 id、`status:"open"`、默认 author/provenance、`screenshot` 相对路径、createdAt/updatedAt）。

### PATCH /api/models/{id}/issues/{issueId}

JSON body：`{"title"?, "comment"?, "status"?}`，仅更新传入字段。

### DELETE /api/models/{id}/issues/{issueId}

删除 Issue 及其截图。

### GET /models/{id}/issues/{file}

Issue 截图静态服务，`file` 必须匹配 `i_[0-9a-f]{12}\.png`。

## 属性 Override 与修改记录

属性修改走 metadata override（不改 IFC 本体）：白名单字段仅 `Name / Description / Classification / FireRating / Comments`；每次修改逐字段写一条 change log。

### GET /api/models/{id}/overrides

返回 `data: { [entityId]: { [field]: value } }`（无 override 时为 `{}`）。

### PUT /api/models/{id}/entities/{entityId}/properties

JSON body：`{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"备注"}}`。

- `fields` 必填且非空；字段名不在白名单返回 `40001 field not in whitelist`。
- 空字符串值 = 清除该字段 override。
- 每个字段写一条 change log（oldValue 为被覆盖前的值；author `local-user`；provenance `UI`）。
- 返回 `data: { [field]: value }`，即该实体当前生效的 override 集合。

### GET /api/models/{id}/changes

返回 `data: ChangeEntry[]`，按 createdAt 降序（无记录时为 `[]`）：

```json
{"code":0,"message":"ok","data":[
  {"id":"c_1a2b3c4d5e6f","entityId":"3a82-xxxx","entityName":"Wall","field":"FireRating","oldValue":"","newValue":"F60","author":"local-user","provenance":{"source":"UI"},"operation":"update","createdAt":"2026-07-29T10:00:00Z"}
]}
```

## 编辑代理端点

Go server 把 edit-service 的端点暴露在 `/api/models/{id}/edit/...` 前缀下（编排：commit 后写 change log、用 IfcDiff 补充 diff、排队重转 XKT）。完整契约见 [IFC 编辑 API](/reference/edit-api)。

## 静态资源（直挂，不走 JSON 信封）

| 路径 | 说明 |
| --- | --- |
| `GET /models/{id}/model.xkt` | XKT 几何数据（支持 Range） |
| `GET /models/{id}/metadata.json` | 元数据（见下） |
| `GET /models/{id}/issues/{file}` | Issue 截图 |

## metadata.json Schema（xeokit 元模型格式）

由 converter 用 web-ifc 从原 IFC 提取（空间结构树 + 属性集），可直接作为 `XKTLoaderPlugin.load({metaModelSrc})` 的输入：

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

约定：`metaObjects[].id` 为 IFC GlobalId（与 XKT entity id 一致）；层级为 Site → Building → Storey → 构件；无 pset 的构件省略 `propertySetIds`。

## 通用错误码

`40001` 参数/校验错误、`40002` 超限、`40400` 模型或 Issue 不存在、`50000` 服务器内部错误。
````

- [ ] **Step 2: 创建 `docs/site/reference/edit-api.md`**

````markdown
# IFC 编辑 API

edit-service（Python FastAPI，默认 `:8100`）是 IFC 编辑端点**唯一参考**。路径参数：`id` 匹配 `^m_[0-9a-f]{16}$`；`guid` 为 IFC GlobalId。除标注外，错误响应为 FastAPI 形态 `{"detail": ...}`。

## 端点目录

### GET /health

健康检查，响应 `{"status": "ok"}`。

### PUT /models/{id}/entities/{guid}

把编辑应用到内存模型并记为一条 pending change（**不落盘**）。先全量校验再应用（单请求原子）：任一校验失败则不产生任何修改。

body（`EditBody`）：

```json
{
  "type": "object",
  "properties": {
    "fields": {"type": "object", "additionalProperties": true, "description": "实体直接属性（Name/Description 等）"},
    "psets": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": true}, "description": "pset 名 → {属性名: 新值}；pset 不存在则创建"},
    "author": {"type": "string", "default": "local-user"},
    "provenance": {"type": "object", "properties": {"source": {"type": "string", "enum": ["UI", "AI"], "default": "UI"}}}
  }
}
```

响应 200（pending entry，同时出现在 pending 与 commit 后 history 中）：

```json
{
  "id": "e_<12位hex>",
  "guid": "...",
  "changes": [{"field": "Name", "oldValue": "...", "newValue": "..."}],
  "author": "ai-agent",
  "provenance": {"source": "AI"},
  "timestamp": "<ISO8601 UTC>"
}
```

`changes[].field`：直接属性用属性名，pset 属性用 `Pset名.属性名`；`oldValue` 取自 IFC 真实值（pset 属性原本不存在时为 `null`）。

错误码：404 模型或 guid 不存在；422 `fields`/`psets` 均为空、未知属性名、值类型不受支持或与 IFC 属性类型不符。

### GET /models/{id}/pending

列出当前 pending（无 pending 返回 `[]`）。注意：pending 与 history 的 GET **不校验模型是否存在**；写路径与 versions/diff 才校验。

### DELETE /models/{id}/pending

丢弃全部 pending：卸载并从磁盘重载内存模型。响应 `{"discarded": <条数>}`；模型不存在 → 404。

### POST /models/{id}/commit

全部 pending 原子落盘（持文件锁）→ 版本快照 → 追加 history（每条补 `operation`）→ 清空 pending。

可选 body：`{"operation": "update" | "migrate"}`，缺省 `"update"`；`migrate` 由 Go 侧 override 迁移传入。响应 200 `{"committed": <条数>, "entries": [...]}`；无 pending → 409；模型不存在 → 404。

### GET /models/{id}/history

持久化编辑历史（含 `operation` 字段），存储于 `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`；无历史返回 `[]`。

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

从未 commit 过时 `versions` 为 `[]`、`current` 为 `null`。

### POST /models/{id}/diff

body：`{"base": "v1", "target": "v2"}`（target 可为 `"current"` 表示 uploads 现态）。响应：

```json
{
  "base": "v1",
  "target": "v2",
  "added": ["<guid>", ...],
  "removed": ["<guid>", ...],
  "changed": [{"guid": "...", "changes": [{"field": "...", "old": ..., "new": ...}]}]
}
```

版本不存在 → 404；缺 `base`/`target` → 422。diff 为属性级（无几何 diff），详见 [版本与 Diff Viewer](/viewer/versions-diff)。

## 经 Go 代理

Go server（默认 `:8090`）把同一套端点暴露在 `/api/models/{id}/edit/...` 前缀下，端点一一对应：

| Go 代理端点 | Python 端点 |
| --- | --- |
| `PUT /api/models/{id}/edit/entities/{guid}` | `PUT /models/{id}/entities/{guid}` |
| `GET /api/models/{id}/edit/pending` | `GET /models/{id}/pending` |
| `DELETE /api/models/{id}/edit/pending` | `DELETE /models/{id}/pending` |
| `GET /api/models/{id}/edit/history` | `GET /models/{id}/history` |
| `GET /api/models/{id}/edit/versions` | `GET /models/{id}/versions` |
| `POST /api/models/{id}/edit/diff` | `POST /models/{id}/diff` |
| `POST /api/models/{id}/edit/commit` | `POST /models/{id}/commit` |

与直连的差异：

- 响应统一包 `{code, message, data}`；错误码映射：404 → 40400、409 → 40900、422 → 40001、其余（含不可达）→ 50200。
- PUT/commit body 若含 `provenance.source`，Go 先校验枚举（UI|AI），非法 → 40001。
- Go 代理 commit 成功后：entries 展开写入 change log、IfcDiff 补充 diff 字段、模型置 `converting` 并排队重转；响应 data 额外含 `"reconverting": true`。
- change log 写失败不返回 500：记日志，响应仍 200，data 含 `"warning"` 字符串（IFC 已落盘、重转已排队，仅 change log 可能缺条）。
````

- [ ] **Step 3: 创建 `docs/site/reference/ai.md`**

````markdown
# AI 接入

面向 AI agent 的接入指南：用 REST 调用 IFC 编辑服务完成「改属性 → pending → commit → diff」全流程。机器可消费的完整 schema 见 [OpenAPI 文件](/reference/openapi)。

## 双角色同一 API

人（浏览器）与 AI agent 使用**同一套编辑端点**，仅入口与 `provenance.source` 不同：

```
浏览器（人）──► Go server :8090 ──代理──► Python 编辑服务 :8100
                  /api/models/{id}/edit/...        │  /models/{id}/...
AI agent ────────► REST 直连 ──────────────────────┘  （或经 Go 代理，端点一一对应）
```

- 人：浏览器 → Go 代理，commit 后 Go 侧写 change log、触发 XKT 重转。
- AI：REST 直连 edit-service（默认 `http://127.0.0.1:8100`），调用时传 `provenance.source="AI"`；也可走 Go 代理。
- Python 服务自带 Swagger UI（`/docs`）与原始 schema（`/openapi.json`）。

## 快速开始

```bash
# 1) Python 编辑服务（默认端口 8100）
cd services/ifc
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server（默认 127.0.0.1:8090）
cd server
go run ./cmd/server
```

**dataDir 一致性**：`VIEWER_DATA_DIR` 必须与 Go `server_config.json` 的 `dataDir` 指向同一目录（两边都按 `{dataDir}/uploads/{id}.ifc` 定位模型文件）。

## AI 直连全流程（curl）

前提：已有一个模型（id 形如 `m_` + 16 位小写 hex），文件在 `{VIEWER_DATA_DIR}/uploads/{id}.ifc`。

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef
GUID='2O2Fr$t4X7ZfFPoeewFlqU'   # IFC GlobalId

# 1. 改属性 → 记入 pending（只改内存，不落盘）
curl -X PUT "$BASE/models/$MID/entities/$GUID" \
  -H 'Content-Type: application/json' \
  -d '{
        "fields": {"Name": "Basic Wall:AI"},
        "psets":  {"Pset_WallCommon": {"FireRating": "2h"}},
        "author": "ai-agent",
        "provenance": {"source": "AI"}
      }'

# 2. 查看 pending
curl "$BASE/models/$MID/pending"

# 3. commit：原子落盘 + 版本快照 + 追加 history
curl -X POST "$BASE/models/$MID/commit"

# 4. 查看版本与 diff
curl "$BASE/models/$MID/versions"
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' \
  -d '{"base": "v1", "target": "current"}'
```

> 直连的 commit **不触发** Go 侧 change log 与 XKT 重转。需要完整链路（前端自动刷新可见）时改走 Go 代理：`http://127.0.0.1:8090/api/models/$MID/edit/...`。

## provenance 与 commit 模型

- `provenance.source`：枚举 `UI | AI`，默认 `UI`。**AI 调用必须传 `"AI"`**。它是声明字段，无防伪语义（v1 无认证）。
- `author`：自由文本，默认 `local-user`。
- 两阶段语义：PUT 只改内存并记 pending；commit 才落盘 + 版本快照 + 写 history。
- commit 模型（Go 侧 change log）：每条 entry 含 `author` / `createdAt` / `operation`（`update | migrate`）/ `diff` / `provenance`。
- Python history 与 Go change log 是两份记录：history 按「一次 PUT = 一条 entry」；change log 按「一个字段变更 = 一条 entry」展开。

## 版本与 diff 语义

- 快照存放于 `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc`（n 从 1 开始，只增不改、原子写）。
- 首次 commit：先把原始上传快照为 v1，再快照新文件为 v2；之后每次 commit 产生 v{n+1}。
- diff 以 GlobalId 为实体标识；changed 归约为实体直接属性与 pset 属性字段级 old→new；entity 引用属性（几何表示层）不参与比较。
- 快照间 diff 结果缓存在 `versions/diff-{base}-{target}.json`；`target="current"` 不缓存。

## 限制与后续路线

v1 已知限制（详见 [已知限制](/project/known-limits)）：单机单用户、无认证（勿暴露公网）；pending 只存内存（服务重启丢失）；`VIEWER_DATA_DIR` 必须与 Go `dataDir` 同目录；diff 仅属性级。

后续路线（**当前未交付**）：MCP 化（REST+MCP 双暴露，参考 ifcmcp 工具模式）与沙箱/代码执行端点——详见 [Roadmap](/project/roadmap)。
````

- [ ] **Step 4: 创建 `docs/site/reference/openapi.md`**

````markdown
# OpenAPI 文件

## edit-service（机器可消费）

完整 OpenAPI schema 见 [ai-tools.openapi.json](/ai-tools.openapi.json)，由实现直接导出（`create_app().openapi()`），与运行中服务的 `GET /openapi.json` 天然一致。

编辑 API 变更后重新生成：

```bash
cd services/ifc
uv run python scripts/export_openapi.py
```

脚本输出到 `docs/site/public/ai-tools.openapi.json`（站点构建时随 public 目录发布）。

## Go server

Go server 的 REST 契约当前以本文档站 [Viewer REST API](/reference/rest-api) 为人工维护的公开契约，没有自动生成的 schema。

> 自动生成与漂移检测（从 schema 生成页面、CI 检测 schema 与已提交产物是否一致）属于后续迭代，见 [Roadmap](/project/roadmap)。
````

- [ ] **Step 5: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`；dist 中存在 `reference/rest-api.html` 等页面。

```bash
git add docs/site/reference
git commit -m "docs: add API & AI reference (REST, edit API, AI integration, OpenAPI)"
```

---

## Task 7: 项目分组（project/）

**Files:**
- Create: `docs/site/project/roadmap.md`
- Create: `docs/site/project/known-limits.md`
- Create: `docs/site/project/contributing.md`
- Create: `docs/site/project/license.md`

- [ ] **Step 1: 创建 `docs/site/project/roadmap.md`**

````markdown
# Roadmap

> 公开版只保留已完成、近期与后续；内部迭代细节见仓库 `docs/internal/`。

## 已完成

- 审查平台：上传/转换、模型树、属性检查、可见性工具、剖切、测量、Issue + 3D Pin、属性 override 与修改历史；issues/overrides/change log 的 File / PostgreSQL 双实现。
- 真改 IFC：edit-service（pending → commit）、版本快照、属性级语义 diff、Diff Viewer、override → 真改迁移。
- AI 接入口：人/AI 双角色编辑 API（provenance 区分）、OpenAPI 工具目录、接入指南。
- 文档站：本 VitePress 站点、PR 构建校验与 GitHub Pages 自动部署。

## 近期

- 部署化：Docker Compose 一键启动（server / web / PostgreSQL / edit-service / converter），配置外置。
- 开源工程化：依赖许可证审计收尾（含 ifcdiff 自包含处理）、示例模型、`v0.1.0` 发布。
- 仓库卫生：Issue/PR 模板、贡献指南完善。

## 后续

- **双语扩展**：中文文档稳定后增加英文 locale；英文优先覆盖首页、快速开始、总体架构、贡献与 API 入口；禁止仅创建空的英文导航或占位页。
- **API 自动生成**：从 edit-service 的 FastAPI OpenAPI schema 生成或同步 API 页面；为 Go server 建立机器可读契约；CI 检测 schema 与已提交产物漂移；人工指南继续解释工作流与语义。
- 编辑 API 的 MCP 封装；几何 diff；增量重转；diff 超时控制。

## v1 范围外

多用户/鉴权、AI 生成 IFC 本体（并行线经编辑 API 接入）、IFC → Python 生成管线、RAG、Git 存 IFC、文档版本切换。
````

- [ ] **Step 2: 创建 `docs/site/project/known-limits.md`**

````markdown
# 已知限制

以下限制是当前实现的真实边界，除特别说明外均属未交付能力而非缺陷：

## 部署与依赖

- **Docker Compose 未完成**：当前只有本地四进程部署方式（见 [环境要求与本地部署](/guide/quickstart)），不支持一键部署。
- **ifcdiff 为本地 editable 依赖**：edit-service 依赖仓库同级目录的 IfcOpenShell 源码 checkout；自包含处理（vendor 或 git source）在 Roadmap 中。
- **模型文件始终文件系统**：PostgreSQL 仅承载 issues / overrides / change log；uploads、XKT、元数据、版本快照仍在文件系统。
- **Python 侧存储仅文件模式**：PG 模式下 edit-service 的 history 与版本快照仍在文件。

## 编辑与并发

- **单机单用户、无认证**：provenance 是声明字段，无防伪语义；请勿将服务暴露到公网。
- **pending 只存内存**：edit-service 重启即丢失未 commit 的修改；history 与版本快照不受影响。
- **无多用户并发控制**：每模型一把锁串行化写，多用户/冲突合并属后续范围。
- **diff 无超时控制**：大模型可能阻塞；有上限。

## 功能边界

- **diff 仅属性级**：不提供几何 diff；entity 引用属性不参与比较。
- **AI 生成 IFC 本体未交付**：AI 通过同一套编辑 API 修改已有模型；生成能力属并行线。
- **MCP 封装未交付**：当前为 REST 形态。
- **OpenAPI 为仓库内静态文件**：自动生成与漂移检测属后续迭代。
- **仅中文文档**：英文 locale 为后续迭代。
````

- [ ] **Step 3: 创建 `docs/site/project/contributing.md`**

````markdown
# 贡献指南

## 开发环境

见 [环境要求与本地部署](/guide/quickstart)。开发采用 TDD：先写失败测试再实现，测试文件与源码同目录。

## 本地验证

```bash
# 后端
cd server && go test ./... && go vet ./...
# 编辑服务
cd services/ifc && uv run pytest
# 前端
cd web && npm test && npm run build
# 转换器
cd converter && npm test
# 文档
cd docs && npm ci && npm run docs:build
```

## 文档贡献

- 公开文档站源在 `docs/site/`，唯一信息源；修改后必须 `cd docs && npm run docs:build` 通过（死链会导致构建失败）。
- `docs/internal/` 与 `docs/archive/` 不进入站点，仅作内部记录与归档。
- 页面涉及未交付能力时，必须标注为 Roadmap，不得提供不可执行步骤。
- 移动或归档文档后，全仓 Markdown 相对链接必须同步更新。

## Commit 与 PR

- Commit 消息遵循仓库惯例：`feat:` / `fix:` / `docs:` / `ci:` / `chore:` 前缀 + 中文或英文简短描述。
- PR 到 `main`：GitHub Actions 会运行现有 viewer CI 与文档构建；两者都必须通过。
- 不提交个人本机路径、密钥、运行时数据（`data/`）。

## License

本仓库为 AGPL-3.0-only。贡献即表示同意以该许可证发布；第三方组件归属见 [License 与第三方组件](/project/license)。
````

- [ ] **Step 4: 创建 `docs/site/project/license.md`**

````markdown
# License 与第三方组件

## 仓库许可证

AI_IFC 以 **AGPL-3.0-only** 发布（[LICENSE](https://github.com/0702hjj/AI_IFC/blob/main/LICENSE)）。许可证继承自 SimpleCADAPI fork，也与 AGPL-3.0 的 xeokit 栈保持一致。

`viewer/` 与 `docs/` 下全部新代码 Copyright (C) 2026 0702hjj（SPDX-License-Identifier 头）。

## 归档代码边界

本仓库 fork 自 SimpleCADAPI（OCP 原生 CAD 生成，论文 artifact）。以下部分保留原始版权与许可证，作为归档参考，**不是**活跃产品：

- `src/simplecadapi/`（SimpleCAD API Team）
- `skills/simplecadapi/`（SimpleCAD API Team）
- `examples/`（SimpleCAD API Team）
- 根 `pyproject.toml`（SimpleCADAPI 包元数据，归档）
- `docs/archive/simplecadapi/`（原 SCAD API/core/stdlib/legacy 文档）

## 第三方组件

完整列表见仓库根 [NOTICE](https://github.com/0702hjj/AI_IFC/blob/main/NOTICE)。要点：

| 组件 | 许可证 |
| --- | --- |
| @xeokit/xeokit-sdk / xeokit-convert | AGPL-3.0 |
| web-ifc | MPL-2.0 |
| ifcopenshell / ifcdiff | LGPL-3.0-or-later |
| pgx (jackc/pgx/v5) | MIT |
| React / Vite / zustand / react-router-dom | MIT |
| FastAPI / uvicorn / pydantic / deepdiff | MIT / BSD-3-Clause |

> ifcdiff 当前以本地 editable 路径依赖引用（未随仓库分发）；发布前将 vendor（保留 LGPL 声明与来源）或固定为 git source，并在 NOTICE 标注。
````

- [ ] **Step 5: 验证构建 + Commit**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`；所有主导航页面均生成 HTML，无占位内容。

```bash
git add docs/site/project
git commit -m "docs: add project section (roadmap, known limits, contributing, license)"
```

---

## Task 8: 文档重组（internal / archive / public 资产）

**Files:**
- Move: `docs/team-sync.md` → `docs/internal/team-sync.md`
- Move: `docs/open-source-plan.md` → `docs/internal/open-source-plan.md`
- Move: `docs/usage.md` → `docs/internal/usage.md`（已迁移，保留为源）
- Move: `docs/ai-integration.md` → `docs/internal/ai-integration.md`（已迁移，保留为源）
- Move: `docs/architecture/*` → `docs/internal/architecture/`（ai-bim / viewer-detail / viewer / viewerstatus / roadmap）
- Move: `docs/architecture/sdk-architecture-review.md` → `docs/archive/simplecadapi/`
- Move: `docs/api/*`、`docs/core/*`、`docs/stdlib/*`、`docs/legacy/*` → `docs/archive/simplecadapi/`（保留各自子目录）
- Move: `viewer/docs/{plan.md,design.md,api.md,README.md}` → `docs/internal/viewer/`
- Move: `docs/ai-tools.openapi.json` → `docs/site/public/ai-tools.openapi.json`（覆盖 Task 1 的副本）
- Modify: `services/ifc/scripts/export_openapi.py`（输出路径）
- Modify: `services/ifc/README.md`（openapi 链接）

- [ ] **Step 1: 创建目录并移动文件**

Run（仓库根）:

````bash
mkdir -p docs/internal/architecture docs/internal/viewer docs/archive/simplecadapi
git mv docs/team-sync.md docs/internal/team-sync.md
git mv docs/open-source-plan.md docs/internal/open-source-plan.md
git mv docs/usage.md docs/internal/usage.md
git mv docs/ai-integration.md docs/internal/ai-integration.md
git mv docs/architecture docs/internal/architecture
mkdir -p docs/archive/simplecadapi
git mv docs/architecture/.gitkeep docs/archive/simplecadapi/ 2>/dev/null || true
git mv docs/api docs/archive/simplecadapi/api
git mv docs/core docs/archive/simplecadapi/core
git mv docs/stdlib docs/archive/simplecadapi/stdlib
git mv docs/legacy docs/archive/simplecadapi/legacy
git mv docs/architecture/sdk-architecture-review.md docs/archive/simplecadapi/sdk-architecture-review.md 2>/dev/null || true
git mv viewer/docs/plan.md docs/internal/viewer/plan.md
git mv viewer/docs/design.md docs/internal/viewer/design.md
git mv viewer/docs/api.md docs/internal/viewer/api.md
git mv viewer/docs/README.md docs/internal/viewer/README.md
git mv docs/ai-tools.openapi.json docs/site/public/ai-tools.openapi.json
````

注意：上面分两次移动 `docs/architecture`（整体移入 internal 后再抽出 sdk-architecture-review 到 archive）；执行时以实际文件为准，`git mv` 失败则调整顺序。移动后：

- `docs/architecture/` 应不存在。
- `docs/api|core|stdlib|legacy` 应不存在。
- `viewer/docs/` 应为空（可删除目录本身，git 不跟踪空目录）。
- `docs/internal/architecture/` 含 ai-bim/viewer-detail/viewer/viewerstatus/roadmap/sdk-architecture-review。
- `docs/archive/simplecadapi/` 含 api/core/stdlib/legacy。

- [ ] **Step 2: 更新 `services/ifc/scripts/export_openapi.py` 输出路径**

把：

```python
OUT = Path(__file__).resolve().parents[3] / "docs" / "ai-tools.openapi.json"
```

改为：

```python
OUT = Path(__file__).resolve().parents[3] / "docs" / "site" / "public" / "ai-tools.openapi.json"
```

同时把 docstring 中 `docs/ai-tools.openapi.json` 改为 `docs/site/public/ai-tools.openapi.json`。

- [ ] **Step 3: 更新 `services/ifc/README.md` 的 openapi 链接**

把 `[docs/ai-tools.openapi.json](../../docs/ai-tools.openapi.json)` 改为 `[docs/site/public/ai-tools.openapi.json](../../docs/site/public/ai-tools.openapi.json)`（若 README 中同时引用 ai-integration.md，一并改为 `../../docs/internal/ai-integration.md`）。

- [ ] **Step 4: 更新 `NOTICE` 中归档文档路径**

把 `docs/legacy/SimpleCADAPI.md` 改为 `docs/archive/simplecadapi/legacy/SimpleCADAPI.md`。

- [ ] **Step 5: 全仓链接清扫**

Run: `rg -n "docs/(api|core|stdlib|legacy|usage|ai-integration|team-sync|open-source-plan|architecture)" --glob '!docs/site/**' --glob '!docs/archive/**' --glob '!docs/internal/**' --glob '!node_modules/**'`
Expected: 除 README/NOTICE/viewer README 等按计划更新的命中外，无残留旧路径。逐条更新：

- 根 `README.md` / `README.zh-CN.md`（Task 9 统一重写，本步先记录命中）。
- `docs/internal/**` 内部的相对链接（如 ai-bim.md 引 `../team-sync.md` 需改为 `../internal/team-sync.md` 或去掉）。
- `viewer/**/README.md` 中指向 `docs/` 的链接改为站内链接或新路径。
- `docs/superpowers/**` 中的链接按需更新（spec 中的路径为规范目标，不强制改；plans 内引用保持历史）。

- [ ] **Step 6: 验证 docs 构建仍通过**

Run（docs/）: `npm run docs:build`
Expected: 退出码 0，`build complete`。

- [ ] **Step 7: Commit**

````bash
git add -A docs services/ifc/scripts/export_openapi.py services/ifc/README.md NOTICE
git commit -m "docs: reorganize docs into site/internal/archive; move SCAD docs out of public site"
````

---

## Task 9: 根 README 指向文档站 + 内部计划记录后续任务

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/internal/architecture/roadmap.md`（记录双语扩展与 API 自动生成）

- [ ] **Step 1: 重写 `README.md`（英文，指向文档站）**

````markdown
# AI_IFC

[中文说明](README.zh-CN.md)

A self-hosted, open-source **BIM review and editing platform** for IFC models — real IFC modification, semantic version diffing, and an AI-ready editing API shared by humans and agents.

> **Documentation: [https://0702hjj.github.io/AI_IFC/](https://0702hjj.github.io/AI_IFC/)** — quick start, viewer usage, development guide, REST/editing API and AI integration.

## What it does

- Upload IFC in the browser; review properties, spatial structure, issues and 3D pins.
- Really edit IFC attributes (override → pending → commit), with immutable version snapshots per commit.
- Compare versions with attribute-level semantic diffs (by GlobalId), rendered in the Diff Viewer.
- Expose the same REST editing API to humans (via the Go server) and AI agents (direct, with `provenance.source="AI"`).

## Quick start

See [Environment & Local Deployment](https://0702hjj.github.io/AI_IFC/guide/quickstart). Four components: `web` (React + xeokit), `server` (Go), `converter` (Node), `services/ifc` (Python FastAPI + IfcOpenShell).

```bash
cd converter && npm install
cd ../edit-service && uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 &
cd ../server && go run ./cmd/server &
cd ../web && npm install && npm run dev
```

Open http://localhost:5173 and upload `converter/test/fixtures/wall-with-opening-and-window.ifc`.

## Repository layout

```
viewer/            # active product: the IFC platform (web / server / converter / edit-service)
docs/site/         # public docs site (VitePress, published to GitHub Pages)
docs/internal/     # internal plans and team sync (not published)
docs/archive/      # archived SimpleCADAPI documentation
src/  skills/  examples/   # archived: SimpleCADAPI (SCAD), the repo's origin
```

## License

[AGPL-3.0-only](LICENSE) — inherited from the SimpleCADAPI fork and consistent with the AGPL-licensed xeokit stack. Third-party attributions and the archived-code boundary: [NOTICE](NOTICE).
````

- [ ] **Step 2: 重写 `README.zh-CN.md`（中文，指向文档站）**

````markdown
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

见文档站 [环境要求与本地部署](https://0702hjj.github.io/AI_IFC/guide/quickstart)。四个组件：`web`（React + xeokit）、`server`（Go）、`converter`（Node）、`services/ifc`（Python FastAPI + IfcOpenShell）。

```bash
cd converter && npm install
cd ../edit-service && uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 &
cd ../server && go run ./cmd/server &
cd ../web && npm install && npm run dev
```

打开 http://localhost:5173 ，上传 `converter/test/fixtures/wall-with-opening-and-window.ifc` 验证。

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
````

- [ ] **Step 3: 在 `docs/internal/architecture/roadmap.md` 记录后续任务**

在「迭代 N+3」节追加：

```markdown
### 后续任务（文档站确认，2026-08-02）

- **双语扩展**：第一版中文文档稳定后再增加英文 locale；英文优先覆盖首页、快速开始、总体架构、贡献和 API 入口；禁止仅创建空的英文导航或内容占位页。
- **API 自动生成**：从 FastAPI OpenAPI schema 生成或同步 edit-service API 页面；为 Go server 建立机器可读规范或等价契约生成方式；CI 检测 schema 与已提交产物是否漂移；人工指南继续解释工作流和语义。
```

（若文件结构有出入，在等价位置追加同样内容。）

- [ ] **Step 4: 验证**

Run: `rg -n "github.io" README.md README.zh-CN.md | head`
Expected: 两个 README 都包含 `0702hjj.github.io/AI_IFC`。

Run（docs/）: `npm run docs:build`
Expected: 退出码 0。

- [ ] **Step 5: Commit**

````bash
git add README.md README.zh-CN.md docs/internal/architecture/roadmap.md
git commit -m "docs: point READMEs at the docs site; record i18n and API auto-gen as follow-ups"
````

---

## Task 10: 总体验收与提交

- [ ] **Step 1: 干净构建验证**

Run:

```bash
rm -rf docs/node_modules docs/package-lock.json docs/site/.vitepress/dist
cd docs && npm ci && npm run docs:build
```

Expected: `npm ci` 成功（锁文件与 package.json 一致）；`docs:build` 退出码 0、`build complete`、无 dead link。

- [ ] **Step 2: 验收标准逐条核对**

| # | 验收标准 | 核对方式 |
| --- | --- | --- |
| 1 | 干净环境 `cd docs && npm ci && npm run docs:build` 成功 | Step 1 输出 |
| 2 | PR 验证构建、main 自动部署 | `.github/workflows/docs.yml` 内容 |
| 3 | 站点可访问、深层页面 base 正确 | 本地 `vitepress preview` 或部署后 curl（Step 4） |
| 4 | 所有主导航页面存在且无占位 | `ls docs/site/{guide,viewer,development,reference,project}` + `rg -n "TODO|TBD|占位" docs/site` 无命中 |
| 5 | 新开发者仅用公开文档可启动四组件并上传样例 | guide/quickstart.md、guide/first-ifc.md 内容 |
| 6 | 编辑/pending/commit/版本/diff 说明与实现一致 | 与 `services/ifc/app/` 及 ai-integration 源核对 |
| 7 | 站点导航与搜索不暴露 SCAD API、内部计划、团队同步 | `rg -n "SimpleCAD|team-sync|N\\+" docs/site`（允许出现「归档」说明性文字，不允许 API 文档/内部叙事） |
| 8 | README 指向正式文档站 | Step 4 of Task 9 |
| 9 | Roadmap 与内部计划记录双语扩展与 API 自动生成 | project/roadmap.md + internal roadmap 内容 |
| 10 | 文档构建、现有 Viewer CI、关键链接检查通过 | Step 1 + 本地跑 `web npm test` 与 `server go test ./...`（若依赖可用） |

- [ ] **Step 3: 链接与内容抽查**

Run: `rg -n "docs/(api|core|stdlib|legacy|usage|ai-integration|team-sync|open-source-plan)" --glob '!docs/archive/**' --glob '!docs/internal/**' --glob '!docs/superpowers/specs/**'`
Expected: 无命中（README/NOTICE 已重写）。

Run: `rg -n "http://localhost|127.0.0.1" docs/site | head`
Expected: 仅示例 base URL 与端口说明，无个人本机路径。

- [ ] **Step 4: 本地预览验证 base 路径**

Run（docs/）:

````bash
npm run docs:build
npx vitepress preview site --port 4173 &
sleep 2
curl -sf http://127.0.0.1:4173/AI_IFC/ | head -5
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4173/AI_IFC/reference/rest-api.html
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:4173/AI_IFC/ai-tools.openapi.json
````

Expected: 首页 200；`reference/rest-api.html` 200；`ai-tools.openapi.json` 200；页面内资源引用以 `/AI_IFC/` 开头。

- [ ] **Step 5: 全量提交**

````bash
git status --porcelain
git add -A
git commit -m "docs: documentation site iteration complete"
````

（若此前任务已全部提交，本步可能无变更。）

- [ ] **Step 6: 推送分支并打开 PR（需批准网络与 git 写权限）**

````bash
git push -u origin iteration-docs-site
gh pr create --title "docs: VitePress documentation site + GitHub Pages deployment" --body "Implements docs/superpowers/specs/2026-08-02-documentation-site-design.md. PR 内验证 docs build；main 合并后自动部署 Pages（需在仓库 Settings → Pages 将 Source 设为 GitHub Actions）。"
````

Expected: 推送成功；PR 创建成功并返回 URL。

- [ ] **Step 7: 验收 CI**

Run: `gh pr checks <PR号> --watch`
Expected: docs build job 与既有 viewer CI 全部通过（converter/server/web/smoke 视依赖可用性）。

---

## Self-Review（写后自查）

- **Spec 覆盖**：§3.1 必须项全部有对应任务（脚手架 T1、首页与导航 T1、内容迁移 T3–T7、合并单一源 T3–T7、校订基线各任务、SCAD/内部移出 T8、PR 构建 + Pages T2、README 指向 T9、计划记录后续 T9）；§3.2 不实现项在 T1 Global Constraints 与内容中排除；§4.1 站点配置逐项落实（lang/base/search/lastUpdated/cleanUrls/editLink/socialLinks）；§4.2 发布流程逐项落实；§5 边界树落实为 T8 的目标目录；§6 导航与侧边栏逐项对应；§7 迁移表逐行覆盖；§8 校订基线全部写入各页；§9 后续迭代记录在 T9；§10 质量规则体现（死链即错误、命令从声明目录执行、Roadmap 标注）；§11 验收标准 = Task 10 Step 2。
- **占位符扫描**：无 TODO/TBD；每个页面都有完整内容。
- **类型一致性**：导航/侧边栏 link 与文件名一一对应（guide/project-intro、guide/quickstart、guide/first-ifc、guide/configuration、viewer/library、viewer/model-tree、viewer/viewing、viewer/issues、viewer/editing、viewer/versions-diff、development/architecture、development/repo-structure、development/web、development/server、development/converter、development/edit-service、development/testing、reference/rest-api、reference/edit-api、reference/ai、reference/openapi、project/roadmap、project/known-limits、project/contributing、project/license）。
