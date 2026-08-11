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
  GO -->|/api/v1/models/{id}/script/* 代理 + 编排| PY
  GO -->|子进程 node convert.js| CV
  GO -->|pgx/v5，可选| PG
  GO --> FS
  PY -->|脚本沙箱执行 / 版本快照 / history| FS
  CV -->|model.xkt + metadata.json| FS
```

## 组件职责

| 组件 | 技术 | 职责 | 选型原因 |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | 审查/编辑/Diff 的全部交互 | xeokit 的 XKT 二进制加载与 BIM 工具链 |
| server | Go 1.26（stdlib net/http + pgx/v5） | 上传/转换队列、REST、编辑编排、存储抽象 | 静态编译、并发模型 |
| converter | Node CLI（web-ifc + xeokit-convert） | IFC → XKT 几何 + 语义提取 | xeokit-convert 只有 npm 形态 |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | 脚本沙箱执行、版本快照（script-as-source）、ScriptMap 定位、语义 diff | IfcOpenShell 是 IFC 编辑的事实标准 |
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

### 编辑流（script-as-source）

web/AI 的修改统一为「改构建脚本」；IFC 是脚本沙箱执行的派生产物。原 L1 直改链路（`PUT /entities/{guid}` → pending → `POST /commit` 真改 IFC）已退役（410，回捞锚点 `fb55a8a`）。

```
PUT /models/{id}/script  {script | params}
  → 契约静态校验（失败 422 零副作用）→ 暂存一步（10 步环窗，落盘恢复，可 undo/redo）
  （plain 模型首次暂存时上传原件保留为 bootstrap.ifc）
POST /models/{id}/script/run      沙箱试运行预览（无版本）
POST /models/{id}/script/save
  → 沙箱跑脚本生成 IFC（失败 422，暂存保留）
  → 大版本 v{n}：scripts/v{n}.py + v{n}.map.json 成对快照（lockstep）
  → versions/v{n}.ifc 只物化最新，历史版本 IFC 快照删除（可按需重建）
  → 有 bootstrap.ifc 时响应带 alignment 对齐计数
（经 Go 代理时，run/save/rollback 成功后：）
  → 转换队列重转 XKT → 前端轮询到 ready 自动重载
```

定位与定向改写：

```
GET /models/{id}/script/locate?guid=
  → 读 IFC Pset_AIIFC.designKey → 查当前 ScriptMap（暂存优先）
  → hit：{line, col, snippet, origin}；miss：200 {"found": false}
POST /models/{id}/script/edit-call  {designKey, argument, value}（仅 edit-service 直连）
  → libcst 标量重写 → 契约校验 + 沙箱重跑 → 成功等同一次暂存；任何失败 422 零副作用
```

### 版本与 diff 流

- 大版本三件成对：`scripts/v{n}.py`（事实源）+ `v{n}.map.json`（定位）全量保留；`versions/v{n}.ifc` 只物化最新，历史版本 diff/下载时从脚本沙箱重建（`ifc_cache/` LRU 4）——确定性 GlobalId 保证语义可对齐，字节不做断言。
- `POST /models/{id}/diff {base, target}`：IfcDiff（`relationships=["attributes","property"]`，从构造上排除几何）给出 added/removed 集合；适配层对 changed 实体自算字段级 old/new；归约为 `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`。
- 快照间 diff 结果缓存（版本不可变，缓存天然有效）；`POST /diff/upload` 对比外部改后 IFC（不落盘不缓存）。

## 版本模型

change log 条目含：`author`（默认 `local-user`，v1 无认证）、`createdAt`（UTC）、`operation`、`provenance`（`{source: UI|AI|USER}`，API 层枚举校验）。版本为线性快照序列（分支/合并未做，属多用户范围）；回滚 = 恢复历史脚本重跑（append-only，不改写历史）。

已知技术债（详见 [已知限制](/project/known-limits)）：历史记录并存（Go change log / edit-service edit-history）粒度与用途不同；diff 无超时控制；Python 侧存储仅文件模式。
