# 开源方案（2026-07-30）

> 目标：把 AI_IFC 以 `v0.1.0` 发布为**自托管开源**项目（docker compose 一键起）。
> 本文是 roadmap §三（迭代 N+3）的细化执行方案。总体架构见 `docs/architecture/ai-bim.md`。

## 一、定位与受众

- **是什么**：IFC 模型的自托管审查 + 编辑平台（真改 IFC、语义 diff、人/AI 双角色编辑 API）
- **受众**：内网/个人自托管的 BIM 团队；做 IFC 工具链的开发者；需要「AI 可接入的 BIM 编辑底座」的研究者
- **不是什么（v1）**：多用户 SaaS（无鉴权）、AI 生成工具本体（AI 生成由并行线经 API 接入）、IFC 全量版本控制系统（Git 半暂缓）
- **卖点差异**：xeokit 级交互体验 + IfcOpenShell 真改 + GlobalId 语义 diff + LLM 可直接消费的 OpenAPI 工具目录

## 二、LICENSE 策略

现状：仓库根 LICENSE 为 **AGPL-3.0**（继承自 SimpleCADAPI fork）。发布前必须完成依赖审计：

| 依赖 | 许可证 | 关注点 |
| --- | --- | --- |
| ifcopenshell / ifcdiff | LGPL-3.0 | 动态链接/独立进程使用通常兼容 AGPL；**ifcdiff 当前是本地 editable 路径依赖，发布前必须处理**（见下） |
| deepdiff（ifcdiff 传递） | MIT | 兼容 |
| pgx/v5 | MIT | 兼容 |
| xeokit-sdk / xeokit-convert | AGPL-3.0 | 同许可证，兼容（这也是保持 AGPL 的现实理由） |
| web-ifc | MPL-2.0 | 兼容 |
| React / Vite / zustand 等 | MIT | 兼容 |
| FastAPI / uvicorn / pydantic | MIT/BSD | 兼容 |

**ifcdiff 处理（N+3 第一批，用户已裁决不在 N+2 做）**：两个候选——
1. **vendor**：拷贝 `ifcdiff.py` 进 `viewer/edit-service/vendor/`，文件头保留 LGPL 声明与来源链接（单文件、零网络依赖，推荐）
2. **git source**：`[tool.uv.sources] ifcdiff = { git = "https://github.com/IfcOpenShell/IfcOpenShell.git", subdirectory = "src/ifcdiff", tag = ... }`（跟随上游，但 clone 整仓慢）

无论哪个，都要在 `viewer/edit-service/README.md` 与 NOTICE 中标注 LGPL 组件来源。

**行动项**：审计每个依赖的实际 LICENSE 文本（`uv pip show` / npm `license` 字段）→ 出 `docs/license-audit.md` 结论表 → 根 NOTICE 文件列三方组件。

## 三、N+3 工程化分解

### 3.1 部署化（docker compose 一键起）

```
services:
  web          # 构建期 npm build，产物交给 server 静态托管或 nginx（二选一，倾向 nginx 简单卷）
  server       # Go 构建（多阶段）；env: VIEWER_PG_DSN / VIEWER_EDIT_SERVICE_URL
  edit-service # python:3.10-slim + uv sync；env: VIEWER_DATA_DIR=/data
  converter    # 非常驻——并入 server 镜像（node + npm ci，server 子进程调用）
  db           # postgres:16（可选 profile：--profile pg 才起；默认文件存储）
volumes:
  viewer-data  # /data（uploads/models，含 versions/history）
```

- 配置外置：`.env.example`（DSN、端口、数据卷路径）；所有端口/host 可配
- 验收：**干净机器 `git clone && docker compose up` → 浏览器可用**（含 edit-service，默认 File 模式）
- 注意：edit-service 与 server 必须共享 `viewer-data` 卷（同一 dataDir 语义）

### 3.2 CI（GitHub Actions）

```yaml
jobs:
  go:        go test ./...（viewer/server）
  python:    uv run pytest（viewer/edit-service；需解决 ifcdiff 来源后才能在 CI 跑）
  web:       npm ci && npm test && npm run build（viewer/web）
  converter: npm ci && npm test（viewer/converter）
  pg:        services: postgres → VIEWER_TEST_PG_DSN 指向该 service，跑 PG store 测试
  smoke:     起 server + edit-service（docker compose 或进程组）→ ./scripts/smoke.sh
```

- 触发：push/PR to main；badge 进 README
- 注意：PG 测试会 DROP 表，DSN 必须指向 CI 的临时 service（已有教训记录）

### 3.3 仓库卫生

- `.gitignore` 复查：`viewer/data/`、`.venv`、`node_modules`、`.superpowers/`、`.pytest_cache`
- 密钥扫描：`gitleaks` 或 GitHub secret scanning 开启
- `.github/ISSUE_TEMPLATE/`（bug / feature）+ `PULL_REQUEST_TEMPLATE.md`
- `CONTRIBUTING.md`（开发环境、测试命令、commit 风格、代码评审要求）
- `CODE_OF_CONDUCT.md`（Contributor Covenant，可选但推荐）

### 3.4 SCAD 遗产归档（已完成大半）

- ✅ 旧 README 已归档至 `docs/legacy/SimpleCADAPI.md`
- 待办：`src/simplecadapi/README`（或现有 README）顶部加 archived 标注；`skills/simplecadapi`、`examples/` 在新 README 已声明归档（已完成）
- 原则：不删除（论文 artifact 有引用价值），但门面完全聚焦 IFC

### 3.5 发布 v0.1.0

1. 上述全部完成 + 文档终审（README 快速开始在干净环境复现）
2. `git tag v0.1.0` + GitHub Release：release notes（特性列表、已知限制、升级说明 N/A）
3. 示例模型：放一个可自由分发的样例 IFC（确认许可证；可用 converter fixture 或公共样例）
4. 可选：`img/` 截图（模型库、3D 审查、Diff Viewer）进 README

## 四、文档体系（当前状态）

| 文档 | 语言 | 状态 |
| --- | --- | --- |
| `README.md` / `README.zh-CN.md` | EN / 中文 | ✅ 已重写（N+3 本文档轮） |
| `docs/usage.md` | 中文 | ✅ 使用文档 |
| `docs/architecture/ai-bim.md` | 中文 | ✅ 总体架构（当前版） |
| `docs/architecture/viewer-detail.md` | 中文 | ✅ viewer 细节 |
| `docs/ai-integration.md` + `docs/ai-tools.openapi.json` | 中文 | ✅ AI 接入（openapi 变更后需 `export_openapi.py` 再导出） |
| `docs/architecture/roadmap.md` / `viewer.md` / `viewerstatus.md` / `research/overview.md` | 中文 | ✅ 活文档，迭代后同步 |
| `docs/open-source-plan.md` | 中文 | ✅ 本文 |
| `docs/license-audit.md` / `CONTRIBUTING.md` / NOTICE | EN | ⬜ N+3 待办 |

原则：**对外门面英文，对内技术文档中文**；README 只放快速路径，细节链到 docs/。

## 五、里程碑与验收

| 序 | 内容 | 验收 |
| --- | --- | --- |
| 1 | ifcdiff 依赖处理 + LICENSE 审计 | `uv sync` 在无 IfcOpenShell 兄弟目录的机器成功；审计表入库 |
| 2 | docker compose | 干净机器一键起，smoke 通过 |
| 3 | CI | 六个 job 全绿（含 PG service、smoke） |
| 4 | 仓库卫生 + SCAD 归档收尾 | gitleaks 干净、模板齐备 |
| 5 | v0.1.0 | tag + release notes + 示例模型 + README 截图 |

排序理由：1 是 2/3 的前置（CI 与镜像都要能装依赖）；2 是验收「自托管」的核心；3 保证后续迭代不回退；4/5 收尾。
