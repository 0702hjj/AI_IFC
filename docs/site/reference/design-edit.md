# 脚本即事实源：Script 编辑与版本对比（辅助设计师）

面向「辅助设计师」的编辑与版本模型：**Python 构建脚本是 IFC 的唯一一一对应表示（script-as-source）**，IFC 是脚本受限执行的派生产物。用户/AI 的修改落在脚本（PARAMS 参数或脚本本体），不做逐步回溯链，只在大版本之间与暂存步之间做轻量对比。

## 边界声明：design JSON 的定位

**design JSON 是 AI 起草阶段的辅助草稿**——它不是模型的完整表示、不是 IFC 的标注文件、不进版本、不参与 diff。**唯一与 IFC 一一对应的是构建脚本**：`scripts/v{n}.py` →（受限执行）→ `versions/v{n}.ifc`。AI 生成复杂模型时可以先产一份 design JSON 草稿辅助构思（见 [aiifc skill](/reference/ai-skill)），但交付物永远是脚本。

## 工作流：plan 草稿 → script → IFC

```
plan / design 草稿（可选，AI 构思辅助，不落版本）
   → 构建脚本 v{n}.py（唯一事实源：PARAMS + build()）
   → 沙箱执行 → IFC v{n}（派生物，可随脚本重建）
```

## 三个核心概念

### 1. 构建脚本（编辑面）

每个 AI 生成模型对应一个完整 Python 构建脚本，遵循脚本契约：

- 头部 `PARAMS = {...}` 顶层字面量 dict（JSON-compatible）：所有可调参数集中于此。
- 确定性身份：构件 GlobalId 由 `uuid5(NAMESPACE_AI_IFC, key)` 派生，并写入 `Pset_AIIFC.designKey`——同一脚本同一 PARAMS 多次运行 GlobalId 不变，跨版本 diff 可对齐。
- **C-locate（契约 #30）**：审查可见构件必须经契约工厂 `script_lib.create_entity(...)` 创建——工厂自动写确定性 GlobalId + `Pset_AIIFC.designKey`，并在运行时记录调用点（行/列/调用行文本/origin）；禁止绕过工厂直接 `root.create_entity`。
- **C-scalar（契约 #31）**：需要 web 端可编辑的参数必须是标量字面量或 PARAMS 引用，不得是任意表达式（否则 edit-call 拒绝，降级为脚本编辑器手改）。
- 入口 `build(params: dict, out_path: str)`；产物必须过 `ifcopenshell.validate`。

### 2. 暂存区（WPS 式，最多 10 步）

脚本编辑（整体替换或仅改 PARAMS）先进入暂存区（最多 10 步，原子落盘、重启自动恢复），支持 undo / redo：

- **放弃** → 丢弃暂存链，**零 diff、零版本**。
- **试运行** → 沙箱执行暂存脚本预览产物，不产生版本。
- **保存** → 跑脚本生成 IFC，脚本 + ScriptMap 成对快照为**大版本**（IFC 只物化最新）。

```
脚本暂存（10 步，落盘恢复，可 undo/redo）
   ├─ 放弃 → 丢弃（无痕）
   ├─ 试运行 → 沙箱跑脚本 → uploads 预览（无版本）
   └─ 保存 → 大版本 v{n}（scripts/v{n}.py + v{n}.map.json；versions/v{n}.ifc 仅最新物化）
```

### 3. 大版本与回退

- **大版本** = 用户/AI 主动保存的点：`models/{id}/scripts/v{n}.py`（+ `v{n}.map.json` 定位 sidecar + `v{n}.meta.json` 备注）全量保留，编号 lockstep。
- **IFC 只物化最新**：`versions/v{n}.ifc` 仅保留最新大版本；历史版本 IFC 在 diff/下载时从对应脚本**按需重建**（沙箱重跑，结果进 `ifc_cache/`，LRU 容量 4）。重建产物与原快照仅语义相等（确定性 GlobalId），字节因 IFC 头时间戳不同——比较一律走语义 diff。
- **回退** = 恢复某版脚本 → 重跑 → IFC（脚本与 IFC 永远一致，不存在「改了 IFC 没改脚本」的分叉）。
- AI 下次介入时的输入：当前脚本 + 脚本 diff + IFC 语义 diff 摘要 → 增量修改而非重写。

## 差异引擎（三层 × 两级）

两级粒度：**大版本**（v{n-1} ↔ v{n}）与**小版本**（暂存链步与步之间，轻量行内 diff），AI 与用户都可见。

| 层 | 对象 | 受众 |
|---|---|---|
| 脚本 unified text diff + PARAMS 键级变更 | `scripts/v{n-1}.py` ↔ `v{n}.py`；暂存步间 | AI（下次输出的上下文）+ 用户（脚本 diff 视图） |
| IFC 语义 diff（ifcdiff，属性级 GlobalId 对齐） | `versions/v{n-1}.ifc` ↔ `v{n}.ifc` | 用户（Diff Viewer，见 [版本对比](/viewer/versions-diff)） |
| 外部上传模型 | 无脚本时走属性级语义 diff（by GlobalId） | 用户 |

## PARAMS 表单与脚本编辑器（前端）

Design 面板解析当前脚本的 `PARAMS` 块自动生成参数表单（ast 提取，不执行脚本）；「下钻」进入脚本编辑器直接改脚本。表单提交 / 脚本保存 = 暂存一步；「保存版本」= 跑脚本 → 大版本。版本对比面板可选两个大版本看脚本 diff 与 IFC 语义 diff，或看暂存链相邻步的小版本 diff。

## 执行安全

edit-service 以 subprocess + 进程组杀死（timeout 60s，`start_new_session` + `killpg`，fork 出的孙进程一并终止）+ rlimits（CPU/内存/NPROC=现有 task 数 +256 余量）+ 独立临时目录执行脚本；失败返回 422 + stderr 截尾 2KB。文件系统与网络隔离分两层：

- **bwrap backend（首选）**：宿主机安装 bubblewrap 包即可用，脚本跑在按需只读挂载 + `--unshare-net` 的沙箱里——沙箱外写操作直接 EROFS，网络不可达。
- **rlimit 降级**：bwrap 不可用时默认 fail-closed（run/save 拒绝执行 503）；开发机显式 `ALLOW_RLIMIT_FALLBACK=1` 才降级为 rlimits + 独立 cwd，此时沙箱外 FS 写与网络**不拦截**；启动日志会打印所用 backend（`script sandbox backend: ...`），部署时确认看到 `bwrap` 字样。

网络可达性取决于部署形态而非「天然无网」：宿主直跑时 edit-service 与其他进程同处一机，脚本沙箱的网络隔离由 bwrap `--unshare-net` 提供；且 edit-service 自身无鉴权，务必只监听 `127.0.0.1:8100`（loopback），外部一律经 Go server 代理。

## API

全部经 Go server（`/api/v1`）代理：

| 端点 | 语义 |
|---|---|
| `GET /api/v1/models/{id}/script` | 当前脚本（暂存态或最近保存） |
| `PUT /api/v1/models/{id}/script` | 暂存一次脚本编辑（整体替换或仅改 PARAMS）；plain 模型首次暂存时自动保留上传原件为 `bootstrap.ifc` |
| `GET /api/v1/models/{id}/script/params` | 当前脚本的 PARAMS dict（ast 提取，不执行） |
| `POST /api/v1/models/{id}/script/undo\|redo\|discard` | 暂存导航 / 放弃 |
| `POST /api/v1/models/{id}/script/run` | 沙箱试运行暂存脚本（预览，无版本） |
| `POST /api/v1/models/{id}/script/save` | 暂存晋升为大版本（跑脚本 + 脚本/map 成对快照）；存在 `bootstrap.ifc` 时响应带 `alignment` 计数（added/removed/changed） |
| `GET /api/v1/models/{id}/scripts` | 大版本列表 |
| `POST /api/v1/models/{id}/script/rollback` | 恢复某版脚本并重跑 |
| `POST /api/v1/models/{id}/script/diff` | 两个大版本的脚本 diff（text + PARAMS 变更） |
| `GET /api/v1/models/{id}/script/staging/diff` | 暂存链步间小版本 diff |
| `GET /api/v1/models/{id}/script/locate?guid=` | guid → designKey → 脚本调用点（line/col/snippet/origin）；miss → 200 `{"found": false}`；暂存与 map 分叉 → 200 `{"found": false, "stale": true}` |

edit-service 直连（`:8100`，不经 Go 代理）另有：

| 端点 | 语义 |
|---|---|
| `POST /models/{id}/script/edit-call` | libcst 标量参数重写（body：`{designKey, argument, value}`）→ 沙箱验证 → 成功等同一次暂存；`origin=traced` / 非标量 / 非法参数名 / 非有限浮点 → 422 零副作用 |

## 定位链路（ScriptMap）

每次沙箱执行 `build()` 时，契约工厂记录每个构件的调用点，`write_and_validate` 落 map sidecar；发布时包为绑定脚本哈希的信封，save 时与脚本 lockstep 快照为 `scripts/v{n}.map.json`：

```python
ScriptMap = dict[designKey, {"line": int, "col": int, "snippet": str,
                             "origin": "literal" | "params" | "traced"}]
# 发布信封（current.map.json / v{n}.map.json）：
# {"scriptHash": sha256(脚本全文), "map": ScriptMap}
```

map 行号只对生成它的那份脚本有效：`PUT /script`（未 run）与 `undo/redo` 会让 staging 与 map 分叉。消费侧按 `scriptHash` 比对 staging 当前脚本：edit-call 对分叉 fail-closed（409，零副作用）；locate 降级为 `{"found": false, "stale": true}`（web 提示先运行脚本，不跳错误行）；旧版裸 map（无信封）一律视为过期。`origin` 决定 web 端改写策略（见 [IFC 脚本编辑](/viewer/editing)）。

## bootstrap：上传 IFC → 脚本

plain 态模型经 AI 复现转为 script-backed：AI 经 MCP 读取上传 IFC → 用 aiifc skill 写复现脚本 → `PUT /script`（平台自动保留上传原件为 `bootstrap.ifc`）→ 沙箱验证 → `script/save` 存 v1。save 响应的 `alignment` 计数（bootstrap 原件 vs 生成 IFC 的属性级语义 diff 摘要）是复现质量的验收信号；对齐计算失败不影响 save 本身（记日志返回 null）。

## 与直改链路（已退役）的关系

- 脚本生成的模型：编辑/版本/差异全部走本页模型（选中 → 定位 → 改写 → 沙箱 → 暂存 → 大版本）。
- 外部上传的 IFC（plain 态）：无编辑入口，仅查看/审查；版本对比走属性级语义 diff（by GlobalId）。
- 原 L1 直改链路（`PUT/DELETE /models/{id}/entities/...`、`POST .../commit` 真改 IFC）**已退役**，端点返回 410 Gone；`POST /models/{id}/diff`（IFC 语义 diff）与 `POST /models/{id}/diff/upload` 保留。
