# AGENTS.md — AI_IFC 人机协同契约

> AI agent 的第一入口。读完本文件即可在不问人的情况下：起服务、跑测试、领工作项、遵守契约。
> 人类入口：README.md · 产品文档：https://0702hjj.github.io/AI_IFC/

## 项目是什么

自托管、开源（Apache-2.0）的 AI 生成平台，提供两个对等逻辑 + 一个可选推荐项（框架 spec：`docs/superpowers/specs/2026-08-11-platform-framework-design.md`）：

- **逻辑一：AI 生成 IFC**（已交付）——`skills/aiifc/` skill 封装 + `services/ifc` 业务逻辑核心的 diff 与 script-as-source 编辑 API（web/AI 修改统一改构建脚本，L1 直改链路已退役 410）；版本快照 + 语义 diff、设计师/AI 双角色同一套 REST 编辑 API。
- **逻辑二：AI 生成 CAD**（skill 域已交付；`services/cad` chunk A+B+C 服务端已交付（骨架/沙箱/REST + diff/locate/edit-call + render.json + Go 代理 + web DXF Canvas 查看器已交付（W-0041），IFC 侧 web-ifc 查看器已交付（W-0044，与 xeokit 并存渐进）；dxf/webifc 编辑面（DesignPanel 全套 + dxf 选中定位脚本）与 viewer.staged 中途预览已交付（W-0045））——`skills/aiplan/`（plan 阶段，管线入口）+ `skills/aidxfv/`（**v3 正式版已上线，唯一迭代基线**；v1/v2 遗留版已于 2026-08-18 删除，原 `AI_CAD/skills/aidxfv*`）+ `skills/aiblueprint-mcp` + `services/cad`（与 ifc 同构）。plan→cad 管线 I/O：aiplan（输入无特殊要求；输出 `plan.json` + `bim_supplement.json`，schema 见 `skills/aiplan/references/schemas/`）→ aidxfv v3（输入 plan.json 只读 + 用户额外描述；输出 `building.json` + 各层 DXF）——契约与说明文档见 `docs/site/reference/ai-skill.md`（公开站），安装/打包见 `docs/site/guide/skills.md`。
- **推荐项：Agent 工作流控制**（已落地：Eino 进程内 chat agent + 主子编排 subagent-as-tool（W-0043），opencode serve 已退役）——提示词资产 `skills/aibim-orchestrator` + `.opencode/`（不再被 server 消费）；代码级 orchestrator 不再追求，原设计见 `2026-08-11-orchestrator-design.md`。

两逻辑共享运行时骨架：`web`（可选前端）/ `server`（Go 网关 :8090）/ `converter`（Node 转换）/ `services/ifc`（Python 业务服务 :8100）/ PostgreSQL（可选）。可复用原则：skill 两个、业务逻辑两个、前端可选、PG 可选、接口可直接调用或移植。

```
浏览器 (React+xeokit/web-ifc 双引擎) ──► Go server :8090（托管 web/dist 静态产物，SPA fallback）──► services/ifc（edit-service :8100, FastAPI+IfcOpenShell）
                               │                  └─ 脚本沙箱执行 + 版本 + diff
                               ├─► server/internal/agent（Eino chat agent 进程内：react loop + 领域工具 + 主子编排）
                               ├─► converter (Node, IFC→XKT)
                               ├─► services/cad（:8200, FastAPI+ezdxf——按 model kind 分流代理，render.json 直挂只读）
AI agent ──► REST 编辑 API ────┘
           └─► skills/aiifc（IFC）/ skills/aidxfv（CAD）（agent 直接写代码）
```

## 组件与命令

| 组件 | 目录 | 测试 | 启动 |
|---|---|---|---|
| web (React 19 + xeokit + web-ifc 双引擎 IFC 查看器 + zustand + Fabric Canvas DXF 查看器) | `web` | `npm test`（vitest，322 用例 / 27 文件）；`npm run lint`（oxlint）；`npm run build`（含 tsc） | `npm run dev`（:5173） |
| server (Go 1.26，stdlib + pgx/v5 + cloudwego/eino) | `server` | `go test ./...`（255 测试，含 18 个 PG 测试需 VIEWER_TEST_PG_DSN，未设自动 skip）；`go vet ./...` | `go run ./cmd/server`（:8090；托管 `web/dist` 静态产物，配置 `webDist`/`VIEWER_WEB_DIST`，默认 `../web/dist`） |
| converter (Node，web-ifc + xeokit-convert) | `converter` | `npm test`（node --test） | 被 server 以子进程调用 |
| edit-service (Python 3.10 + FastAPI + ifcopenshell) | `services/ifc` | `uv run --group dev pytest`（258 测试） | `VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100` |
| cad-edit-service (Python 3.10 + FastAPI + ezdxf) | `services/cad` | `uv run --group dev pytest`（225 测试） | `VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8200` |
| mcp-server (Python + mcp 2.x MCPServer，stdio) | `mcp` | `uv run --group dev pytest`（20 测试） | `uv run python -m app.server`（薄包 edit-service REST，解析用户改后 IFC/DXF 并标 USER） |
| skill 打包 | `tools/skill_pack.py`（泛化打包器：`--skill <name>` 默认 aiifc，`--skill-dir <path>` 任意 skill） | `python -m pytest tests/skill/ -q`（142 测试 +2 skip，CI 用独立 .ci-venv） | `python tools/skill_pack.py --archive`（默认 aiifc；`--skill-dir skills/aidxfv/v3 --archive` 打 CAD v3；`--skill-dir skills/aiplan --archive` 打 plan） |
| 端到端 | `scripts/smoke.sh` | 需 server 运行 | 上传→转换→下载 |
| 文档站 | `docs/` | `npm run docs:build`；`npm run check:api`（API 文档漂移检测） | `npm run docs:dev`；内部 wiki `npm run docs:dev:internal` |

## 测试纪律（硬规则）

1. **新代码必须有契约/单测，新增测试量 ≥ 新增实现量（≥1:1）**；关键路径（契约、回滚、沙箱、状态机）加码。（2026-08-07 由 ~3 倍目标调整为现实口径，原目标见 git 历史）
2. 修 bug：先写**复现该 bug 的失败测试**，再改实现，测试转绿才允许 commit。
3. 新功能：TDD，先失败测试后实现。
4. 测试与源码同目录（`*_test.go` / `*.test.ts(x)` / `test_*.py`）。
5. **异步写盘必须等落地**：涉及 `convert.Queue`、SSE、后台 goroutine 等异步写盘的测试，结束（尤其 `t.TempDir()` 清理）前必须用**条件等待**（轮询状态 + 超时）确认异步完成——禁止固定 sleep。教训：2026-08-06 main CI flake（TestCreateProjectViaChatPath，PR #12）。

## 代码门控（硬规则）

1. **按职责拆分模块**：任何源码与文档文件不得超过 **500 行**；接近上限即按领域/职责重构拆分，不等到撞线。
2. **正常排版**：不得通过压缩代码、合并无关语句来规避行数限制。
3. 代码清晰、函数职责单一；避免无意义的 clone、阻塞异步执行器、不受控的内存增长。

机器强制：`scripts/check_file_size.sh`（CI `file-size-gate` job）；存量超限登记在 `scripts/file_size_whitelist.txt`（只减不增，新超限变红）；自动生成物/golden/wasm/research 镜像文档由脚本按类别豁免。白名单内的文件是重构候选，碰到顺手拆。

## 校验与业务隔离（硬规则）

1. 业务规则校验必须住在 `verify*`/`validate*` 函数里；handler 内禁止内联 `if + raise HTTPException`（Python）/ `if + writeErr`（Go）的业务规则检查——请求形状校验归声明式层（pydantic `Field(pattern=...)`、解码），不在此列。handler 只做：decode → verify → 调领域 → 翻译错误。
   - Python 范例：`services/ifc/app/routes_scripts.py` 的 `verify_script_body` / `verify_params_target` / `verify_script_contract`；纯函数校验器范例 `skills/aiifc/references/docs/flows/script_lib.py` 的 `validate_script_contract()`（返回错误列表，与执行分离）。
   - Go：校验归 domain 包的 `validate()`/`Valid*()` + 哨兵错误，handler 只做 解码 → 调用 → `errors.Is` 翻译。
2. 看到 `verify*`/`validate*` 函数名，新增检查只允许加在该函数内部，不得在调用点另写。
3. 跨文件的请求解析/校验 helper 只允许单点定义（edit-service 统一在 `app/route_common.py`），禁止复制第二份。
4. `verify*`/`validate*` 只做检查（可返回派生数据），禁止副作用/写盘/IO——防止其变成第二个业务层。校验隔离机器强制（契约测试）：`tests/test_verify_isolation.py`（Python，`raise HTTPException` 只准出现在 verify*/validate* 或 `route_common.py`）+ `internal/api/api_verify_isolation_test.go`（Go，handler 不得内联非 400 的 `writeErr`），存量违规以白名单登记，新违规变红。

## 纪律事件化（硬规则）

一切纪律优先落为**事件触发的机器检查**（CI job、hook、契约测试），其次才是本文档的文字约定——不要让人/reviewer 轮询违规，让环境在事件（push/PR/文件写入）发生时唤起。多任务执行（SDD）同理：controller 不轮询子代理中间态，子代理报告文件即事件载荷，任务级 review 是事件触发的 gate。新立规矩时先问：能不能写成机器检查？

## 部署形态变更（硬规则）

部署形态为**宿主直跑**（无 Docker，2026-08-19 起）：`scripts/`（smoke/安装/启动脚本）、`.github/workflows/`、server 静态托管（`web/dist`）链路的变更 = **部署形态变更**。本机测试套件对 CI 环境与目标宿主机环境（bwrap/userns 可用性、文件属主、端口占用）零证明力：

1. PR 描述必须标注部署形态的验证方式（本机实际跑过的命令与结果，或「未经本地验证，CI smoke 为唯一防线」）；
2. 合并前必须亲眼看 CI 绿（含 e2e smoke job），禁止 `--auto` 合并后走人；
3. smoke 失败先 `gh run view --job <id> --log` 拿日志再改，禁止盲改重推。

教训：2026-08-19 W-0047 容器形态连续三次 compose smoke 红（共享卷 uid 属主 → bwrap 被宿主 AppArmor 拦 userns）；为在非 root 容器里跑 bwrap 先后打了 setuid 与 apparmor=unconfined 两个洞，容器层对沙箱服务名存实亡，实证后部署形态改为宿主直跑（bwrap 原生可用）。

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

- `skills/aiblueprint-mcp`：fork 自 thebossnow/aiblueprint-mcp（MIT）——改动注意保留 MIT 归属（SKILL.md frontmatter 归属声明），勿与主仓 Apache 文件混排。`skills/aidxfv/v1`（含 vendored cadpy/archdxf）与 `skills/aidxfv/v2`（均 fork 自 earthtojake/text-to-cad，MIT）**已于 2026-08-18 删除**（v3 正式版上线为唯一基线）；其中主仓 Apache-2.0 的 flows 契约层（cad_script_lib）迁入 `services/cad/flows/`。`skills/aiplan/` 与 `skills/aidxfv/v3/` 同为 MIT 自包含。
- SCAD 遗产（`src/`、`skills/simplecadapi/`、根打包配置）已于 2026-08-06 移至私有归档仓 [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive)，本仓不含，勿引用。
- `docs/site/public/` 下的自动生成物（`go-rest-api.routes.json` 等）：只经 `npm run gen:api` 更新。
- `data/`：运行时数据，gitignored，不要手工改。
- 内部文档（`docs/internal/`、`docs/work/`、`docs/superpowers/`）的内容**不得**复制进 `docs/site/`（公开站）。

## 环境注意

- 沙箱后端：bwrap 优先，缺失时 rlimit 降级**默认 fail-closed**（run/save 拒绝执行 503）；本地开发机无 bwrap 时需显式 `ALLOW_RLIMIT_FALLBACK=1`（生产勿设，W-0047）。沙箱资源/并发限额 env：`SCRIPT_RUN_CONCURRENCY`、`SCRIPT_MAX_FSIZE_BYTES`、`SCRIPT_MAX_OUTPUT_BYTES`、`SCRIPT_MAX_PRODUCT_BYTES`（两服务同名同义）。
- 部署形态：宿主直跑（无 Docker）。生产由 Go server 托管 `web/dist`（`webDist`/`VIEWER_WEB_DIST`），浏览器只访问 :8090；开发走 vite dev server :5173。
- edit-service 与 Go server 共享 `VIEWER_DATA_DIR`：两边必须指向同一 `data` 绝对路径，配错会 404 或改错文件。
- demo/flows 用 `services/ifc/.venv`（含 ifcopenshell/ifcquery；ezdxf 不在其中，DXF 依赖用 `services/cad/.venv`）；**根 `.venv` 没有这些包**。
- AI agent 直连 edit-service :8100 时传 `provenance.source="AI"`。
- chat agent LLM 三参 `VIEWER_LLM_API_KEY` / `VIEWER_LLM_BASE_URL` / `VIEWER_LLM_MODEL`（server_config.json 同名字段 `llmAPIKey`/`llmBaseURL`/`llmModel`）；**API key 为空时回退 scriptedModel 离线模式**（确定性 mock，不产生真实智能回复）；`VIEWER_OPENCODE_URL` 已退役无效果。
- Go server 鉴权默认关闭（`apiToken`/`VIEWER_API_TOKEN` 为空）；设置后除 OPTIONS 与 `GET /v1/models/...` 只读文件外全部端点要 `Authorization: Bearer <token>`（401 envelope 码 `40100`）。CORS 为白名单制（`corsOrigins`/`VIEWER_CORS_ORIGINS`，默认 `http://localhost:5173,http://localhost:8080`）。edit-service :8100 与 cad-edit-service :8200（同约束）无鉴权，务必保持 127.0.0.1；AI agent 直连 :8100/:8200 绕过 token 校验。
