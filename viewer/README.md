# IFC Web Viewer

基于 Web 的 IFC 模型审查平台：上传 IFC 文件，后台转换为 XKT 格式，在浏览器中通过 xeokit 进行三维可视化、构件拾取、属性审查、模型树搜索/过滤、显隐控制、剖切、测量与 Issue/Markup 审查协同。

## 功能

- **模型库**：上传（≤200MB）、转换状态轮询、重试、下载、删除
- **三维查看**：xeokit 渲染、轨道旋转/缩放、NavCube、构件拾取高亮
- **模型树**：搜索（名称/类型）、IFC 类型过滤、逐节点显隐、点击定位
- **可见性工具栏**：隐藏选中 / 隔离 / X-Ray / 重置可见性
- **属性面板**：Pset 分组折叠、属性搜索、属性复制；白名单字段（Name/Description/Classification/FireRating/Comments）可编辑，保存为 metadata override 覆盖显示并带修改标记
- **Issue/Markup**：选中构件创建 Issue（自动保存相机视角 + 截图）、状态流转（Open/Checking/Resolved）、点击恢复视角、删除；3D Issue Pin（HTML overlay 钉，点击定位）
- **修改历史**：IssuePanel「修改历史」tab 展示 change log（实体/字段/old→new/时间），每次属性修改自动记录
- **AI 聊天**：项目页聊天侧边栏（可拖拽宽度），对话式让 AI agent 改/生成 IFC；流式渲染 markdown 文本 / 工具调用详情 / 思考链，可中途停止；agent 修改经 Go 固定代码自动落盘（commit + 版本快照 + 重转 XKT），刷新即见
- **工具**：剖切（X/Y/Z 滑杆）、距离测量

## 架构

系统由三个模块组成：

- **converter**（Node.js）：IFC → XKT 转换器，基于 web-ifc。被 server 以子进程方式调用，无需常驻进程。
- **server**（Go，stdlib + pgx/v5）：HTTP API 服务（默认端口 `:8090`），负责模型上传、转换任务调度、XKT/元数据静态服务、模型管理、Issue CRUD、属性 override 与修改记录，以及 AI 聊天代理（chat 模块，转发 opencode serve 并触发 AI 改动的落盘流水线）。
- **web**（React + xeokit）：前端应用（开发端口 `:5173`），包含模型库页面与三维审查界面（含聊天侧边栏）。
- **opencode serve**（opencode CLI server 模式，默认 `:4096`）：承载 AI agent，由 Go chat 模块代理调用（见下「AI 聊天」章节）。

详细设计、API 契约与测试说明已并入公开文档站：[Viewer REST API](https://0702hjj.github.io/AI_IFC/reference/rest-api) 与 [测试与调试](https://0702hjj.github.io/AI_IFC/development/testing)；本文仅保留源码邻近的最小启动提示。

```
web (React/xeokit)  ──HTTP──>  server (Go :8090)  ──子进程──>  converter (Node)
                                      │  ├── edit-service (Python :8100)  IFC 真改
                                      │  └── opencode serve (:4096)        AI agent
                                      └── data/  (上传的 IFC、生成的 XKT 与元数据、
                                                  issues/changes/overrides 持久化)
```

Issue / 属性 override / 修改记录三类持久化默认均为文件存储（`internal/{issue,override,change}.Store` 接口抽象）。配置后切换为 PostgreSQL（`PgStore`，pgx/v5 驱动，启动自动建表 `issues/changes/overrides`，API/前端零改动）：

```json
// server/server_config.json
{"pgDSN": "postgres://user:pass@host:port/dbname"}
```

也可设环境变量 `VIEWER_PG_DSN`（优先级高于配置文件）。未配置时保持文件存储，无需任何数据库。

## IFC 真改（edit-service）

`edit-service/`（Python FastAPI，默认 `:8100`）通过 ifcopenshell 对 IFC 做真实修改：pending（内存）→ commit（落盘 + 版本快照）。Go server 作为编排层代理其接口，并在 commit 成功后写 change log、自动重转 XKT；另提供 override → 真改迁移。

**关键约束：两服务必须读写同一数据目录** —— edit-service 的 `VIEWER_DATA_DIR` 必须与 server 配置的 `dataDir` 指向同一目录（如 `viewer/data`），否则会出现 404 或改的不是同一份文件。

```bash
# 终端：IFC 编辑服务（:8100）
cd edit-service && uv sync && VIEWER_DATA_DIR=../data uv run uvicorn app.main:app --port 8100

# 验证：健康检查
curl http://127.0.0.1:8100/health    # → {"status":"ok"}
```

> 服务依赖 `ifcopenshell` / `ifcdiff` 均为 PyPI 官方发布（对齐 IfcOpenShell 0.8.5），`uv sync` 直接安装，无需本机 IfcOpenShell 源码或软链。aiifc skill 的 flows 另需 `ifcquery`（见 `skills/aiifc/requirements.txt`）。

配置（环境变量）：`VIEWER_DATA_DIR`（默认 `../data`，须与 server 一致）、`EDIT_SERVICE_PORT`（默认 8100）。Go 侧配置：

```json
// server/server_config.json
{"editServiceURL": "http://127.0.0.1:8100"}
```

也可设环境变量 `VIEWER_EDIT_SERVICE_URL`（优先级高于配置文件），默认 `http://127.0.0.1:8100`。

Go 侧端点（均走 `{code,message,data}` envelope，透传 Python 状态码语义：404→404、409→409、422→400、不可达→502）：

| 端点 | 说明 |
| --- | --- |
| `PUT /api/v1/models/{id}/edit/entities/{guid}` | 代理：暂存一条 pending 修改（body `{fields?, psets?, author?, provenance?}`） |
| `GET /api/v1/models/{id}/edit/pending` / `DELETE` | 查询 / 丢弃 pending |
| `POST /api/v1/models/{id}/edit/commit` | 编排：commit → 写 change log（含 diff 补充）→ 重转 XKT，响应 `{committed, entries, reconverting}`；change log 写失败降级为 `warning` 字段（仍 200，重转照常排队） |
| `GET /api/v1/models/{id}/edit/history` | 编辑历史 |
| `GET /api/v1/models/{id}/edit/versions` | 版本快照列表 |
| `POST /api/v1/models/{id}/edit/diff` | 版本间 diff（body `{base, target}`，target 可为 `current`） |
| `POST /api/v1/models/{id}/overrides/migrate` | 把该模型全部 override 回放为真实 IFC 修改（一次 commit 一个版本快照，commit 带 `operation=migrate`），成功字段清除 override，失败字段保留并返回 `{migrated, failed}`；change log 写失败降级为 `warning` 字段 |

## AI 聊天（opencode serve）

`opencode serve`（opencode CLI 的 server 模式，默认端口 `:4096`）承载 AI agent。Go server 的 chat 模块（`internal/opencode/` 客户端 + `api/chat.go`）代理其会话/消息接口，并把 opencode SSE 事件流透传给前端聊天侧边栏；agent 直接读写 `{dataDir}/uploads/{id}.ifc`，修改完成后由 Go 内固定代码自动三连（丢 pending → pset 标记 → commit 落盘 + 版本快照 + 重转 XKT），前端刷新即见 AI 改动。

**关键约束：opencode serve 的工作目录必须是 demo 适配环境 `IFC_front/AI_IFC/`**（viewer 的上级目录），而不是 `viewer/` —— 该目录含适配的 `opencode.json`（模型 `zhipuai-coding-plan/glm-5.2`、`skills.paths=["skills"]`）、`skills/aiifc`（IFC 技能）与 `.opencode/agent/ifc-demo.md`（demo agent 规则），与开发环境 `CADapi/AI_IFC` 隔离。

```bash
# 终端：AI 聊天（:4096）
# ⚠️ 必须用绝对路径 cd 到 AI_IFC：工作目录错了会读不到 opencode.json（model/skills/agent 全丢）→ unknown error
cd ~/.code/gaiahub/CADapi/IFC_front/AI_IFC && opencode serve --port 4096 --cors http://localhost:5173

# 验证：① 健康检查；② 启动日志首行应为 loading .../AI_IFC/opencode.json（确认工作目录对）
curl http://127.0.0.1:4096/global/health    # → {"healthy":true,...}
```

Go 侧配置（仿 editServiceURL 模式）：

```json
// server/server_config.json
{"openCodeURL": "http://127.0.0.1:4096"}
```

也可设环境变量 `VIEWER_OPENCODE_URL`（优先级高于配置文件），默认 `http://127.0.0.1:4096`。

chat 模块端点（均走 `{code,message,data}` envelope，opencode 原生格式不透出）：

| 端点 | 说明 |
| --- | --- |
| `POST /api/v1/chat/sessions` | 建/复用会话（同 modelId 幂等复用），持久化到 `{dataDir}/chat-sessions.json` |
| `GET /api/v1/chat/sessions` | 会话列表 |
| `POST /api/v1/chat/sessions/{cid}/messages` | 发消息给 AI agent（body `{text}`） |
| `GET /api/v1/chat/sessions/{cid}/messages` | 会话历史（回填聊天内容） |
| `GET /api/v1/chat/sessions/{cid}/events` | SSE 透传：agent 流式消息 + chat 模块自有事件（`viewer.committed` 等） |
| `POST /api/v1/chat/sessions/{cid}/abort` | 中止 AI 当前 turn（透传 opencode `/session/{id}/abort`） |
| `POST /api/v1/chat/projects` | 骨架项目：生成空白 IFC（含用户命名）→ 注册模型 → 入队转换（从零构建入口） |

## 依赖版本

- Node.js ≥ 18
- Go ≥ 1.22
- python3 ≥ 3.10 + [uv](https://docs.astral.sh/uv/)（edit-service：FastAPI + ifcopenshell；`uv sync` 需 ifcdiff 本地路径）
- opencode CLI（AI 聊天可选，`opencode serve` 需要；见上「AI 聊天」章节）

## 快速启动（本机验证）

```bash
# 0. 一次性：安装依赖
cd converter && npm install && cd ../web && npm install && cd ..
cd edit-service && uv sync && cd ..     # 需 ifcdiff 本地路径可达（见上）

# 1. 终端 1：后端（:8090）
cd server && go run ./cmd/server

# 2. 终端 2：前端（:5173，/api 与 /models 已代理到 :8090）
cd web && npm run dev

# 3. 终端 3：IFC 编辑服务（:8100，VIEWER_DATA_DIR 须与 server 的 dataDir 一致）
cd edit-service && VIEWER_DATA_DIR=../data uv run uvicorn app.main:app --port 8100

# 4. 终端 4（可选，AI 聊天）：opencode serve（:4096）
#    ⚠️ 必须绝对路径 cd 到 AI_IFC（不是 IFC_front！）：工作目录错了读不到 opencode.json → unknown error
cd ~/.code/gaiahub/CADapi/IFC_front/AI_IFC && opencode serve --port 4096 --cors http://localhost:5173

# 5. 浏览器打开 http://localhost:5173 ，上传 .ifc 验证
```

> 起 AI 聊天服务后，项目页聊天侧边栏才可用（`POST /api/v1/chat/*` 不可达时返回 502，不影响模型浏览）。

端到端冒烟（覆盖上传→转换→下载→Issue CRUD→属性 override/修改记录 全链路，需 server 已运行；edit-service 可达时追加 edit flow 段，否则自动跳过）：

```bash
./scripts/smoke.sh    # 成功输出以 smoke OK 结尾
```

运行测试：

```bash
cd converter && npm test          # 转换器集成测试
cd server && go test ./...        # 后端 56 个测试
cd web && npm test                # 前端 84 个测试（另：npm run build 类型检查）
```

## 目录说明

```
viewer/
├── converter/        IFC→XKT 转换器（Node.js）
│   └── test/fixtures/  测试用 IFC 文件
├── server/           后端 API 服务（Go）
│   ├── cmd/server/     服务入口
│   ├── internal/opencode/  opencode serve 客户端（AI 聊天）
│   ├── internal/issue/ Issue 存储（Store 接口 + File/Pg 双实现）
│   ├── internal/change/ 修改记录 change log（Store 接口 + File/Pg 双实现）
│   ├── internal/override/ 属性 override（白名单字段，Store 接口 + File/Pg 双实现）
│   └── server_config.json
├── web/              前端应用（React + xeokit + Vite，含聊天侧边栏）
├── edit-service/     IFC 真改服务（Python FastAPI + ifcopenshell，pending/commit + 版本快照）
│   ├── app/             FastAPI 应用（config/main/routes_edits/routes_diff/versions/history/registry）
│   └── scripts/export_openapi.py  OpenAPI schema 导出（docs/ai-tools.openapi.json）
├── scripts/smoke.sh  端到端冒烟脚本（含 Issue CRUD + override/changes）
├── docs/             设计文档、API 文档、计划
└── data/             运行时数据（不纳入版本管理）
    ├── uploads/          IFC 文件（AI agent 直接读写此处）
    ├── staging/          AI 交付脚本暂存区
    ├── chat-sessions.json  AI 会话映射持久化（原子写）
    └── models/{id}/      版本快照 versions/、脚本 scripts/ 等

# AI 侧（opencode serve 工作目录，在 viewer/ 上级）
IFC_front/AI_IFC/
├── opencode.json          模型、skills.paths（demo 适配版）
├── skills/aiifc/          IFC 技能（demo 适配版）
├── .opencode/agent/ifc-demo.md   demo agent 规则（staging/自检/原子替换）
└── .venv/                 Python 环境（按 skills/aiifc/requirements.txt 安装：ifcopenshell + ifcquery + numpy）
```
