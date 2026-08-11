# AGENTS.md — AI_IFC 人机协同契约

> AI agent 的第一入口。读完本文件即可在不问人的情况下：起服务、跑测试、领工作项、遵守契约。
> 人类入口：README.md · 产品文档：https://0702hjj.github.io/AI_IFC/

## 项目是什么

自托管、开源（AGPL-3.0）的 AI 生成平台，提供两个对等逻辑 + 一个可选推荐项（框架 spec：`docs/superpowers/specs/2026-08-11-platform-framework-design.md`）：

- **逻辑一：AI 生成 IFC**（已交付）——`skills/aiifc/` skill 封装 + `services/ifc` 业务逻辑核心的 diff 与 script-as-source 编辑 API（web/AI 修改统一改构建脚本，L1 直改链路已退役 410）；版本快照 + 语义 diff、设计师/AI 双角色同一套 REST 编辑 API。
- **逻辑二：AI 生成 CAD**（skill 域已交付，diff/编辑 API 待建）——`skills/aidxfv/`（v1/v2，原 `AI_CAD/skills/aidxfv*`）+ `skills/aiblueprint-mcp` + `services/cad`（待建，与 ifc 同构）。
- **推荐项：Agent 工作流控制**（可选，做不好可删）——orchestrator + 事件总线，设计见 `2026-08-11-orchestrator-design.md`。

两逻辑共享运行时骨架：`web`（可选前端）/ `server`（Go 网关 :8090）/ `converter`（Node 转换）/ `services/ifc`（Python 业务服务 :8100）/ PostgreSQL（可选）。可复用原则：skill 两个、业务逻辑两个、前端可选、PG 可选、接口可直接调用或移植。

```
浏览器 (React+xeokit) ──► Go server :8090 ──► services/ifc（edit-service :8100, FastAPI+IfcOpenShell）
                               │                  └─ 脚本沙箱执行 + 版本 + diff
                               ├─► converter (Node, IFC→XKT)
AI agent ──► REST 编辑 API ────┘
           └─► skills/aiifc（IFC）/ skills/aidxfv（CAD）（agent 直接写代码）
```

## 组件与命令

| 组件 | 目录 | 测试 | 启动 |
|---|---|---|---|
| web (React 19 + xeokit + zustand) | `web` | `npm test`（vitest，194 用例 / 20 文件）；`npm run lint`（oxlint）；`npm run build`（含 tsc） | `npm run dev`（:5173） |
| server (Go 1.26，stdlib + pgx/v5) | `server` | `go test ./...`（138 测试，含 18 个 PG 测试需 VIEWER_TEST_PG_DSN，未设自动 skip）；`go vet ./...` | `go run ./cmd/server`（:8090） |
| converter (Node，web-ifc + xeokit-convert) | `converter` | `npm test`（node --test） | 被 server 以子进程调用 |
| edit-service (Python 3.10 + FastAPI + ifcopenshell) | `services/ifc` | `uv run --group dev pytest`（242 测试） | `VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100` |
| mcp-server (Python + mcp 2.x MCPServer，stdio) | `mcp` | `uv run --group dev pytest`（20 测试） | `uv run python -m app.server`（薄包 edit-service REST，解析用户改后 IFC/DXF 并标 USER） |
| skill 打包 | `tools/skill_pack.py`（泛化打包器：`--skill <name>` 默认 aiifc，`--skill-dir <path>` 任意 skill） | `python -m pytest tests/skill/ -q`（147 测试，CI 用独立 .ci-venv） | `python tools/skill_pack.py --archive`（默认 aiifc；`--skill-dir skills/aidxfv/v1 --archive` 打 CAD） |
| 端到端 | `scripts/smoke.sh` | 需 server 运行 | 上传→转换→下载 |
| 文档站 | `docs/` | `npm run docs:build`；`npm run check:api`（API 文档漂移检测） | `npm run docs:dev`；内部 wiki `npm run docs:dev:internal` |

## 测试纪律（硬规则）

1. **新代码必须有契约/单测，新增测试量 ≥ 新增实现量（≥1:1）**；关键路径（契约、回滚、沙箱、状态机）加码。（2026-08-07 由 ~3 倍目标调整为现实口径，原目标见 git 历史）
2. 修 bug：先写**复现该 bug 的失败测试**，再改实现，测试转绿才允许 commit。
3. 新功能：TDD，先失败测试后实现。
4. 测试与源码同目录（`*_test.go` / `*.test.ts(x)` / `test_*.py`）。
5. **异步写盘必须等落地**：涉及 `convert.Queue`、SSE、后台 goroutine 等异步写盘的测试，结束（尤其 `t.TempDir()` 清理）前必须用**条件等待**（轮询状态 + 超时）确认异步完成——禁止固定 sleep。教训：2026-08-06 main CI flake（TestCreateProjectViaChatPath，PR #12）。

## 校验与业务隔离（硬规则）

1. 业务规则校验必须住在 `verify*`/`validate*` 函数里；handler 内禁止内联 `if + raise HTTPException`（Python）/ `if + writeErr`（Go）的业务规则检查——请求形状校验归声明式层（pydantic `Field(pattern=...)`、解码），不在此列。handler 只做：decode → verify → 调领域 → 翻译错误。
   - Python 范例：`services/ifc/app/routes_scripts.py` 的 `verify_script_body` / `verify_params_target` / `verify_script_contract`；纯函数校验器范例 `skills/aiifc/references/docs/flows/script_lib.py` 的 `validate_script_contract()`（返回错误列表，与执行分离）。
   - Go：校验归 domain 包的 `validate()`/`Valid*()` + 哨兵错误，handler 只做 解码 → 调用 → `errors.Is` 翻译。
2. 看到 `verify*`/`validate*` 函数名，新增检查只允许加在该函数内部，不得在调用点另写。
3. 跨文件的请求解析/校验 helper 只允许单点定义（edit-service 统一在 `app/route_common.py`），禁止复制第二份。
4. `verify*`/`validate*` 只做检查（可返回派生数据），禁止副作用/写盘/IO——防止其变成第二个业务层。校验隔离机器强制（契约测试）：`tests/test_verify_isolation.py`（Python，`raise HTTPException` 只准出现在 verify*/validate* 或 `route_common.py`）+ `internal/api/api_verify_isolation_test.go`（Go，handler 不得内联非 400 的 `writeErr`），存量违规以白名单登记，新违规变红。

## 纪律事件化（硬规则）

一切纪律优先落为**事件触发的机器检查**（CI job、hook、契约测试），其次才是本文档的文字约定——不要让人/reviewer 轮询违规，让环境在事件（push/PR/文件写入）发生时唤起。多任务执行（SDD）同理：controller 不轮询子代理中间态，子代理报告文件即事件载荷，任务级 review 是事件触发的 gate。新立规矩时先问：能不能写成机器检查？

## API 契约

- Go server 是唯一对外入口，对外路径统一 `/api/v1/{resource}/{id}`。
- 响应统一 envelope `{code, message, data}`，`code=0` 成功；**新增/修改端点必须包 envelope 并配契约测试**。
- 编辑统一走 script-as-source：`PUT /script`（暂存）→ `script/run`（沙箱）→ `script/save`（大版本，`scripts/v{n}.py` + `v{n}.map.json` 全留、`versions/v{n}.ifc` 只留最新）；定位 `GET /script/locate?guid=`；`POST /script/edit-call`（libcst 标量改写）仅在 edit-service 直连暴露。L1 直改端点（`/entities/...`、`/commit`）已退役返回 410，回捞锚点 `fb55a8a`。
- 改 API 后必须：`cd docs && npm run gen:api && npm run check:api`（漂移检测会拦 PR）。openapi 源 schema 变更时先跑 `services/ifc/scripts/export_openapi.py`。
- modelId 格式 `^m_[0-9a-f]{16}$`；issue 截图、上传大小等限制见 `server/internal/api/api.go`。

## Git 工作流（硬规则）

- 远程 `main` **受保护**：GitHub ruleset 按用户 bypass（owner 已自加）。docs-only 小修（`*.md`、计数/指针/措辞级）允许直推 main；**任何代码变更与大改一律开分支走 PR**（`feat/...`、`fix/...`、`docs/...`）。判断不了大小就走 PR。
- 用 gh-cli 提 PR：`gh pr create`；CI（ci.yml 8 job + docs.yml 3 job）绿后合并；合并后删本地/远程分支。
- **PR 节奏（2026-08-07 用户裁决）：一天最多 1 个 PR**——工作项在同一迭代分支上累积，当天收工时一次性提 PR（分支随取随用 `feat/|fix/|docs/<主题>`）；只有 main 红了的 hotfix 才单独提。
- commit 信息中文、前缀式（`feat(server): ...` / `fix(web): ...` / `docs: ...` / `chore: ...`）。
- 多任务实施计划默认用 superpowers:subagent-driven-development 执行（每任务派 fresh subagent + 任务级 review + 全分支终审）；进度记入 `.superpowers/sdd/<plan>/progress.md` ledger。

## 工作项流程

1. 从 `docs/work/items/` 选 `open` 项（规则见 `docs/work/README.md`）。
2. 置 `in-progress`，填执行者/分支。
3. 按 item 的「方案/验收标准/测试要求」执行；测试要求是硬条件。
4. 完成后置 `done`、填关闭 commit/PR，并在 `docs/work/PLAN-v0.1.0.md` 勾掉 milestone 行。

## 边界（不要碰）

- `skills/aidxfv/v1`（含 vendored cadpy/archdxf）与 `skills/aiblueprint-mcp`：fork 自 earthtojake/text-to-cad（MIT）——改动注意保留 MIT 归属（其 LICENSE 文件），勿与主仓 AGPL 文件混排。
- SCAD 遗产（`src/`、`skills/simplecadapi/`、根打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不含，勿引用。
- `docs/site/public/` 下的自动生成物（`go-rest-api.routes.json` 等）：只经 `npm run gen:api` 更新。
- `data/`：运行时数据，gitignored，不要手工改。
- 内部文档（`docs/internal/`、`docs/work/`、`docs/superpowers/`）的内容**不得**复制进 `docs/site/`（公开站）。

## 环境注意

- edit-service 与 Go server 共享 `VIEWER_DATA_DIR`：两边必须指向同一 `data` 绝对路径，配错会 404 或改错文件。
- demo/flows 用 `services/ifc/.venv`（含 ifcopenshell/ezdxf/ifcquery）；**根 `.venv` 没有这些包**。
- AI agent 直连 edit-service :8100 时传 `provenance.source="AI"`。
- Go server 鉴权默认关闭（`apiToken`/`VIEWER_API_TOKEN` 为空）；设置后除 OPTIONS 与 `GET /v1/models/...` 只读文件外全部端点要 `Authorization: Bearer <token>`（401 envelope 码 `40100`）。CORS 为白名单制（`corsOrigins`/`VIEWER_CORS_ORIGINS`，默认 `http://localhost:5173,http://localhost:8080`）。edit-service :8100 无鉴权，务必保持 127.0.0.1；AI agent 直连 :8100 绕过 token 校验。
