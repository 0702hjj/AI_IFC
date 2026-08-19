# services/ifc：独立部署与调用

> 复用性承诺：`services/ifc/` 是 IFC 业务逻辑核心（diff + script-as-source 编辑 API），**可脱离 Go server / web / converter / PostgreSQL 独立部署与调用**，也可整体移植到新宿主。它是与 `skills/aiifc/` skill 配对的服务端运行时——skill 产出构建脚本，本服务负责沙箱执行、版本快照与语义 diff。

## 是什么

- **独立进程**：FastAPI（Python 3.10+ + ifcopenshell + ifcdiff），默认 `:8100`。
- **两个核心能力**：
  1. **script-as-source 编辑 API**——一切修改落在构建脚本上（`PUT /script` 暂存 → `script/run` 沙箱试运行 → `script/save` 大版本），IFC 只是脚本的构建产物。
  2. **diff**——版本间 / 当前态的 GlobalId 级字段级语义 diff（`POST /diff`、`POST /diff/upload`），几何噪声天然过滤。
- **历史**：原 viewer/edit-service 业务核心，物理重组后为 `services/ifc/`；L1 直改端点（pending → commit 真改 IFC）已退役返回 410。

## 独立部署

前置：Python 3.10+ 与 [uv](https://docs.astral.sh/uv/)。依赖（`ifcopenshell` / `ifcdiff`）均为 PyPI 官方发布（对齐 IfcOpenShell 0.8.5），`uv sync` 直接安装，**无本地源码依赖**。

```bash
cd services/ifc
uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100
```

启动后自带 Swagger UI（`http://127.0.0.1:8100/docs`）与原始 schema（`/openapi.json`），`GET /health` 返回 `{"status": "ok"}`。

### 配置环境变量

| 环境变量 | 默认 | 说明 |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | 模型数据根目录。**推荐用绝对路径**；默认值相对进程 CWD 解析（在 `services/ifc/` 下启动即顶层 `data/`）。与 Go `dataDir` 同目录语义 |
| `AIIFC_FLOWS_DIR` | `../../skills/aiifc/references/docs/flows` | aiifc skill flows 目录（沙箱执行需要其中的 `script_lib.py` 做脚本契约校验）。相对路径相对 `services/ifc/` 根解析（与 CWD 无关） |
| `EDIT_SERVICE_PORT` | `8100` | 监听端口 |
| `EDIT_SERVICE_MAX_MODELS` | `8` | 内存模型缓存（LRU）上限 |

### 模型文件布局

模型 id 必须匹配 `^m_[0-9a-f]{16}$`，对应 `uploads/{id}.ifc`：

```
{VIEWER_DATA_DIR}/
├── uploads/
│   └── m_<16hex>.ifc            # 当前模型态（script/run 或 save 时原子替换）
└── models/
    └── m_<16hex>/
        ├── bootstrap.ifc        # plain 模型首次暂存脚本时保留的上传原件（§5.4）
        ├── current.map.json     # ScriptMap 信封 {"scriptHash", "map"}（run 时发布）
        ├── scripts/
        │   ├── v1.py            # 大版本脚本（全保留，lockstep 编号）
        │   ├── v1.map.json      # 大版本 ScriptMap（全保留）
        │   └── v1.meta.json     # 版本元信息（note / savedAt）
        ├── versions/
        │   └── v1.ifc           # 只物化最新；历史按需从脚本重建（ifc_materialize）
        └── edit-history.json    # 编辑历史（user-edits 追加，原子写）
```

### 沙箱后端要求（宿主运行）

服务以普通用户直接在宿主机运行即可。bwrap 沙箱走 unprivileged user namespace：Debian/Ubuntu 安装 `bubblewrap` 包即可用；RHEL 系确认 `user.max_user_namespaces > 0`。无 bwrap 时沙箱默认 **fail-closed**（run/save 拒绝执行，503）；开发机可显式 `ALLOW_RLIMIT_FALLBACK=1` 降级为 rlimit 模式（FS/网络隔离弱化），生产环境勿设。启动日志会打印所用后端（`script sandbox backend: ...`），部署时确认看到 `bwrap` 字样。

与完整平台的关系：**本服务只是业务核心**。对外完整链路（envelope 包装、鉴权、上传→转换→浏览）仍需 Go server + converter；AI agent 也可直连 :8100 调编辑 API（传 `provenance.source="AI"`）。直连无鉴权——保持监听 127.0.0.1 或仅内网可达，勿暴露公网。

## 可调用端点全清单

错误响应为 FastAPI 形态 `{"detail": ...}`；**直连时无 `{code, message, data}` envelope**——envelope 是经 Go server 代理时统一包装（`code=0` 成功，见 [IFC 编辑 API](/reference/edit-api)）。机器可读 schema 见 [编辑 API 参考（自动生成）](/reference/edit-api-reference)。

### script-as-source 编辑（`app/routes_scripts.py`）

| 端点 | 语义 |
| --- | --- |
| `GET /models/{id}/script` | 当前脚本（暂存态或最后保存的大版本） |
| `PUT /models/{id}/script` | 暂存一次编辑：body 恰好二选一 `{"script": ...}`（整体替换）或 `{"params": {...}}`（仅改 PARAMS 块，服务端 ast 改写） |
| `GET /models/{id}/script/params` | ast 提取当前脚本 PARAMS（不执行） |
| `POST /models/{id}/script/undo` · `redo` · `discard` | 暂存导航（10 步）/ 放弃暂存 |
| `POST /models/{id}/script/run` | 沙箱试运行暂存脚本到 uploads（预览，无版本） |
| `POST /models/{id}/script/save` | 晋升大版本：跑脚本 + `scripts/v{n}.py` + `v{n}.map.json` + `versions/v{n}.ifc` 成对快照 |
| `GET /models/{id}/scripts` | 大版本列表（scripts + versions） |
| `POST /models/{id}/script/rollback` | 把某大版本脚本回暂存并重跑到 uploads |
| `POST /models/{id}/script/diff` | 两个大版本的脚本 diff（文本 diff + PARAMS 变化 + 统计） |
| `GET /models/{id}/script/staging/diff?from=&to=` | 两个暂存步之间的小 diff（默认最近两步） |
| `GET /models/{id}/script/locate?guid=` | guid → designKey → 调用点（line/col/snippet/origin）；miss → 200 `{"found": false}` |
| `POST /models/{id}/script/edit-call` | libcst 标量参数改写 + 沙箱验证 + 暂存一步完成；**仅直连暴露，不经 Go 代理** |

### diff 与版本（`app/routes_diff.py`）

| 端点 | 语义 |
| --- | --- |
| `GET /models/{id}/versions` | 版本快照列表 + 当前版本 |
| `POST /models/{id}/diff` | body `{"base": "v1", "target": "v2"}`（target 可为 `"current"`）；GlobalId 级 `added/removed/changed` 字段级语义 diff |

### 只读 pending / history 与 user-edits（`routes_edits.py` / `routes_user_edits.py`）

| 端点 | 语义 |
| --- | --- |
| `GET /models/{id}/pending` | 当前 pending（直改退役后仅作 script-run 回放簿记，不承载用户编辑） |
| `DELETE /models/{id}/pending` | 丢弃 pending |
| `GET /models/{id}/history` | 持久化编辑历史（只读；新增记录来自 `user-edits`） |
| `POST /models/{id}/user-edits` | 把外部用户修改事件（`origin: "ifc-upload"|"dxf-upload"`）登记进 history，stamped `source="USER"` |
| `POST /models/{id}/diff/upload` | multipart 上传用户改后 IFC 与现态对比（不落盘、不缓存），响应多 `labels` |

### 退役端点（410 Gone）

`PUT/DELETE /models/{id}/entities/{guid}`、`GET .../editable-schema`、`POST /models/{id}/commit` 返回 410——直接改 IFC 已退役，一切修改走构建脚本（回捞锚点 `fb55a8a`）。

## 可缺省边界

services/ifc 之外的所有组件都是**可选的**。下表列「没有它，services/ifc 还能干什么 / 缺什么」：

| 组件 | 没有它时 | 缺什么 |
| --- | --- | --- |
| **Go server**（:8090） | 独立提供全部编辑 / diff / 版本 REST 端点（REST 直连 :8100） | 统一 `{code,message,data}` envelope、`/api/v1` 对外入口、鉴权（`Authorization: Bearer`）、run/save 后 XKT 重转编排、与浏览器会话的桥接 |
| **web**（React 前端） | 无 UI 依赖，纯 API 调用不受影响 | 可视化（xeokit 3D 浏览）、模型树 / 属性面板 / 脚本编辑器 / Diff Viewer |
| **converter**（Node） | 编辑与 diff 完全可用 | IFC → XKT 渲染转换（web 可视化必需） |
| **PostgreSQL** | 编辑与 diff 完全可用（默认文件存储） | issues / changes / overrides 的 PG 持久化（可选存储抽象） |

模型上传（`uploads/{id}.ifc`）与 `data/` 布局是唯一的数据约定——任何组件只要按同一 `VIEWER_DATA_DIR` 写 `uploads/{id}.ifc` 即可被编辑服务使用。

## 移植指南

搬到新宿主的最小步骤：

1. 拷贝 `services/ifc/` 与 `skills/aiifc/`（沙箱执行需要其 flows 里的 `script_lib.py`）。
2. `cd services/ifc && uv sync`（PyPI 依赖，无需本地 IfcOpenShell 源码）。
3. 配置 `VIEWER_DATA_DIR`（绝对路径）指向你的模型数据根目录；必要时设 `AIIFC_FLOWS_DIR`。
4. `uv run uvicorn app.main:app --port 8100` 启动；Swagger UI 自检。

与 skill 的衔接：脚本契约见 aiifc SKILL.md **MUST #25-31**——顶层 `PARAMS` 字面量 dict、构件经 `script_lib.create_entity` 工厂创建（确定性 GlobalId + `Pset_AIIFC.designKey` + 调用点记录）、`build(params, out_path)` 入口、出口过 `script_lib.write_and_validate`（`ifcopenshell.validate`）。服务端的静态契约校验与沙箱执行（`app/script_runner.py`）以 flows 目录为唯一依赖。完整接入（双角色架构、curl 全流程、provenance/commit 模型）见 [AI 接入](/reference/ai)。

## 诚实边界

- **无鉴权**：:8100 直连无 token 校验，务必保持监听 127.0.0.1，勿暴露公网。要对外鉴权走 Go server。
- **provenance 是声明字段**：`provenance.source`（AI/UI/USER）由调用方自报，服务端只做枚举校验，不验证身份。
- **沙箱执行依赖**：run/save 依赖 ifcopenshell + aiifc flows（`script_lib` 契约校验）；无 bwrap 时沙箱默认 fail-closed（503），显式 `ALLOW_RLIMIT_FALLBACK=1` 才降级为 rlimit（沙箱外 FS 写与网络不拦截）。
- **缓存语义**：内存模型缓存有上限（`EDIT_SERVICE_MAX_MODELS`）；暂存只存内存（服务重启丢未 run 暂存），大版本落盘持久。
