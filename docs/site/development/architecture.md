# 总体架构

```mermaid
graph LR
  subgraph 客户端层
    UI[浏览器<br/>React 19 + xeokit<br/>viewer/web]
    AI[AI Agent]
  end

  subgraph 服务层
    GO[Go server :8090<br/>viewer/server<br/>编排 / REST / 存储抽象]
    PY[Python edit-service :8100<br/>viewer/edit-service<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>viewer/converter<br/>IFC → XKT + metadata.json]
  end

  subgraph 存储层
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(文件系统<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|同一套编辑 API| PY
  AI -->|或经 Go 代理| GO
  GO -->|/api/v1/models/{id}/edit/* 代理 + 编排| PY
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

已知技术债（详见 [已知限制](/project/known-limits)）：三份历史记录并存（Go change log / edit-service edit-history / 内存 pending）粒度与用途不同；pending 为内存态；diff 无超时控制；Python 侧存储仅文件模式。
