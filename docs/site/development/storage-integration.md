# 存储接口契约（整合进已有数据库）

本文面向想把平台存储层对接到自有数据库/文件系统的集成方。一切签名与路径以代码为准：`server/internal/store/store.go`、`server/internal/{issue,change,override}/`、`server/cmd/server/main.go`。

## 两种存储实现

- **文件存储（默认，零依赖）**：全部状态落在 `dataDir`（`server_config.json` 的 `dataDir`，edit-service 侧为 `VIEWER_DATA_DIR`）指向的数据目录，JSON 文件 + tmp+rename 原子写。
- **PostgreSQL（可选）**：设 `VIEWER_PG_DSN`（或配置文件 `pgDSN`）即切换。装配逻辑在 `server/cmd/server/main.go`：`PgDSN` 非空时 issue/change/override 三个存储切到 `NewPgStore`，三张表（`issues` / `changes` / `overrides`）由各自 `pgstore.go` 里的 `CREATE TABLE IF NOT EXISTS` 自动建立，schema 见 `server/internal/{issue,change,override}/pgstore.go`。

注意两处不对称（以代码为准）：

1. **模型注册表不进 PG**——`store.Store`（模型元数据 `model.json` + 上传件 `uploads/{id}.ifc`）无论是否启用 PG 始终是文件存储，PG 只承接 issue/change/override 的网关侧状态。
2. **issue 截图不进 PG**——PG 模式下 PNG 仍落盘 `models/{id}/issues/{issueId}.png`（`issue/pgstore.go` 复用 dataDir 写截图），库内只存相对路径。

## 数据目录布局

Go server 与 services/ifc（edit-service）**必须共享同一 `VIEWER_DATA_DIR` 绝对路径**——两边都按 `{dataDir}/uploads/{id}.ifc` 定位模型文件，配错会 404 或改错文件。

```
{VIEWER_DATA_DIR}/
├── uploads/
│   └── {id}.ifc                    # 原始上传 IFC（Go store.IFCPath）
└── models/{id}/
    ├── model.json                  # 模型状态：name/size/status/error（Go store，原子写）
    ├── model.xkt                   # converter 产物（GET /v1/models/{id}/model.xkt 服务）
    ├── metadata.json               # converter 产物（xeokit 元模型）
    ├── issues.json                 # issue 列表（仅文件存储模式）
    ├── issues/{issueId}.png        # issue 截图（文件/PG 模式均在此）
    ├── changes.json                # 修改记录（仅文件存储模式）
    ├── overrides.json              # 属性 override（仅文件存储模式）
    ├── edit-history.json           # services/ifc 持久化编辑历史
    ├── pending.json                # script-run 回放簿记（内部）
    ├── script_staging.json         # 暂存脚本链
    ├── bootstrap.ifc               # 首次暂存脚本时保留的上传原件
    ├── current.map.json            # 当前 ScriptMap 发布信封
    ├── scripts/                    # 大版本脚本快照：v{n}.py + v{n}.map.json 全留
    ├── versions/                   # 大版本 IFC：v{n}.ifc 只留最新
    └── ifc_cache/                  # diff/下载时按需重建的历史版本 IFC + .map.json sidecar
```

`uploads/` 与 `models/{id}/model.json`、`model.xkt`、`metadata.json`、issues/changes/overrides 由 Go server 与 converter 写；`bootstrap.ifc`、`current.map.json`、`scripts/`、`versions/`、`ifc_cache/`、`edit-history.json`、`pending.json`、`script_staging.json` 由 services/ifc 直接读写（不经 Go store）。

## 第三方整合路径

按耦合从高到低三条路：

1. **实现 Go store 接口**（用自己的数据库承接网关侧状态）。三个接口均在对应包的 `issue.go` / `change.go` / `override.go`：

   | 接口 | 方法 | 职责 |
   | --- | --- | --- |
   | `issue.Store` | `List` / `Create` / `Update` / `Delete` / `DeleteModel` / `SaveScreenshot` | issue CRUD、按模型清理、截图落盘（返回相对路径） |
   | `change.Store` | `List` / `Append` / `DeleteModel` | 修改记录追加与按模型清理 |
   | `override.Store` | `GetAll` / `Set` / `DeleteModel` | 属性 override 读写（`Set` 返回被覆盖前的旧值）与按模型清理 |

   注意：模型注册表 `store.Store` 是具体 struct 不是接口，换它的存储需要改 server 内部装配（`cmd/server/main.go`）。

2. **复用本仓 PG schema**：直接把三个 `pgstore.go` 的 `CREATE TABLE IF NOT EXISTS` 语句建到自己的 PG 实例，设 `VIEWER_PG_DSN` 指向它，与既有表共存/federation。

3. **仅文件级对接**：直接读写 `VIEWER_DATA_DIR` 目录（最低耦合，适合只读消费 XKT/metadata 或旁路分析）。写方必须遵守与 server 一致的并发写纪律：tmp 文件 + rename 原子替换，禁止原地截断写。

## 边界

- services/ifc（edit-service）直接读写文件目录，不经过 Go store；Go 与 Python 共享的是**目录契约**，不是内存中的 store 实例。
- PG 只存 override/change/issue 等网关侧状态（以各 `pgstore.go` 实际为准）；脚本、版本、ScriptMap、编辑历史始终在文件目录。
- `data/` 是运行时数据目录（gitignored），不要手工改。
