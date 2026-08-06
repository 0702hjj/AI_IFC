# AGENTS.md — AI_IFC 人机协同契约

> AI agent 的第一入口。读完本文件即可在不问人的情况下：起服务、跑测试、领工作项、遵守契约。
> 人类入口：README.md · 产品文档：https://0702hjj.github.io/AI_IFC/

## 项目是什么

自托管、开源（AGPL-3.0）的 IFC 审查与编辑平台：真改 IFC（pending→commit）、版本快照 + 语义 diff、人/AI 双角色同一套 REST 编辑 API、aiifc 建模 skill。

```
浏览器 (React+xeokit) ──► Go server :8090 ──► edit-service :8100 (FastAPI+IfcOpenShell)
                               │                  └─ 真改 IFC + 版本 + diff
                               ├─► converter (Node, IFC→XKT)
AI agent ──► REST 编辑 API ────┘
           └─► skills/aiifc/（agent 直接写 ifcopenshell.api 代码）
```

## 组件与命令

| 组件 | 目录 | 测试 | 启动 |
|---|---|---|---|
| web (React 19 + xeokit + zustand) | `viewer/web` | `npm test`（vitest，107 用例）；`npm run lint`（oxlint）；`npm run build`（含 tsc） | `npm run dev`（:5173） |
| server (Go 1.26，stdlib + pgx/v5) | `viewer/server` | `go test ./...`（100 测试，含 18 个 PG 测试需 VIEWER_TEST_PG_DSN，未设自动 skip）；`go vet ./...` | `go run ./cmd/server`（:8090） |
| converter (Node，web-ifc + xeokit-convert) | `viewer/converter` | `npm test`（node --test） | 被 server 以子进程调用 |
| edit-service (Python 3.10 + FastAPI + ifcopenshell) | `viewer/edit-service` | `uv run --group dev pytest`（54 测试） | `VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100` |
| skill 打包 | `tools/skill_pack_aiifc.py` | `python -m pytest tests/skill/ -q`（9 测试，CI 用独立 .ci-venv） | `python tools/skill_pack_aiifc.py --archive` |
| 端到端 | `viewer/scripts/smoke.sh` | 需 server 运行 | 上传→转换→下载 |
| 文档站 | `docs/` | `npm run docs:build`；`npm run check:api`（API 文档漂移检测） | `npm run docs:dev`；内部 wiki `npm run docs:dev:internal` |

## 测试纪律（硬规则）

1. **测试量目标 ≈ 实现代码的 3 倍**（经验比例 ~75% 内容用于测试）。
2. 修 bug：先写**复现该 bug 的失败测试**，再改实现，测试转绿才允许 commit。
3. 新功能：TDD，先失败测试后实现。
4. 测试与源码同目录（`*_test.go` / `*.test.ts(x)` / `test_*.py`）。
5. **异步写盘必须等落地**：涉及 `convert.Queue`、SSE、后台 goroutine 等异步写盘的测试，结束（尤其 `t.TempDir()` 清理）前必须用**条件等待**（轮询状态 + 超时）确认异步完成——禁止固定 sleep。教训：2026-08-06 main CI flake（TestCreateProjectViaChatPath，PR #12）。

## API 契约

- Go server 是唯一对外入口，对外路径统一 `/api/v1/{resource}/{id}`。
- 响应统一 envelope `{code, message, data}`，`code=0` 成功；**新增/修改端点必须包 envelope 并配契约测试**。
- 改 API 后必须：`cd docs && npm run gen:api && npm run check:api`（漂移检测会拦 PR）。
- modelId 格式 `^m_[0-9a-f]{16}$`；issue 截图、上传大小等限制见 `viewer/server/internal/api/api.go`。

## Git 工作流（硬规则）

- 远程 `main` **受保护，禁止直推**。一切改动开分支：`feat/...`、`fix/...`、`docs/...`。
- 用 gh-cli 提 PR：`gh pr create`；CI（ci.yml 6 job + docs.yml）绿后合并；合并后删本地/远程分支。
- commit 信息中文、前缀式（`feat(server): ...` / `fix(web): ...` / `docs: ...` / `chore: ...`）。
- 多任务实施计划默认用 superpowers:subagent-driven-development 执行（每任务派 fresh subagent + 任务级 review + 全分支终审）；进度记入 `.superpowers/sdd/<plan>/progress.md` ledger。

## 工作项流程

1. 从 `docs/work/items/` 选 `open` 项（规则见 `docs/work/README.md`）。
2. 置 `in-progress`，填执行者/分支。
3. 按 item 的「方案/验收标准/测试要求」执行；测试要求是硬条件。
4. 完成后置 `done`、填关闭 commit/PR，并在 `docs/work/PLAN-v0.1.0.md` 勾掉 milestone 行。

## 边界（不要碰）

- SCAD 遗产（`src/`、`skills/simplecadapi/`、根打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不含，勿引用。
- `docs/site/public/` 下的自动生成物（`go-rest-api.routes.json` 等）：只经 `npm run gen:api` 更新。
- `viewer/data/`：运行时数据，gitignored，不要手工改。
- 内部文档（`docs/internal/`、`docs/work/`、`docs/superpowers/`）的内容**不得**复制进 `docs/site/`（公开站）。

## 环境注意

- edit-service 与 Go server 共享 `VIEWER_DATA_DIR`：两边必须指向同一 `viewer/data` 绝对路径，配错会 404 或改错文件。
- demo/flows 用 `viewer/edit-service/.venv`（含 ifcopenshell/ezdxf/ifcquery）；**根 `.venv` 没有这些包**。
- AI agent 直连 edit-service :8100 时传 `provenance.source="AI"`。
- Go server 鉴权默认关闭（`apiToken`/`VIEWER_API_TOKEN` 为空）；设置后除 OPTIONS 与 `GET /v1/models/...` 只读文件外全部端点要 `Authorization: Bearer <token>`（401 envelope 码 `40100`）。CORS 为白名单制（`corsOrigins`/`VIEWER_CORS_ORIGINS`，默认 `http://localhost:5173,http://localhost:8080`）。edit-service :8100 无鉴权，务必保持 127.0.0.1；AI agent 直连 :8100 绕过 token 校验。
