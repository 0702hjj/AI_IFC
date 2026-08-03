# Viewer 详细技术文档（2026-07-30，迭代 N+2 后）

> 总体架构见 [ai-bim.md](./ai-bim.md)；迭代计划见 [roadmap.md](./roadmap.md)；现状评估见 [viewerstatus.md](./viewerstatus.md)。
> 本文面向维护者，按组件讲清「代码在哪、接口是什么、怎么验证」。

## 一、组件总览

```
viewer/
├── web/           React 19 + TS + Vite + zustand + xeokit-sdk（:5173 dev）
├── server/        Go 1.26（stdlib + pgx/v5）（:8090）
├── converter/     Node CLI（web-ifc + xeokit-convert）
├── edit-service/  Python 3.10 + FastAPI + ifcopenshell + ifcdiff（:8100，uv 项目）
├── data/          运行数据（uploads/ + models/{id}/，gitignored）
├── scripts/       smoke.sh 端到端验证
└── docs/          design.md 等设计文档
```

## 二、web（`viewer/web/`）

### 目录与组件树

```
src/
├── App.tsx                 路由：/ → LibraryPage，/view/:id → ViewerPage
├── api/
│   ├── client.ts           request<T> 解包 {code,message,data}；全部 API 函数
│   └── types.ts            ModelInfo / Issue / ChangeEntry / OverridesMap / DiffResponse…
├── pages/
│   ├── LibraryPage.tsx     上传（拖拽，.ifc ≤200MB）、状态轮询（2s）、retry/删除/下载
│   └── ViewerPage.tsx      ViewerProvider + Toolbar + ModelTreePanel + PropertyPanel
│                           + IssuePanel；模型状态轮询（converting→ready 触发 XKT 重载）
└── viewer/
    ├── ViewerContext.tsx   xeokit Viewer + XKTLoaderPlugin（xkt + metadata 双加载）；
    │                       context = {viewer, sceneModel, metaModel}；含 IssuePins overlay
    ├── ModelTreePanel.tsx  空间树（搜索/类型过滤/显隐，默认展开 1 层）
    ├── PropertyPanel.tsx   pset 展示（搜索/折叠/复制）+ 白名单字段行内编辑（override）
    ├── IssuePanel.tsx      Issues / 修改历史 双 tab；新建 Issue（相机 + canvas 截图）
    ├── IssuePins.tsx       3D HTML 钉 overlay（每帧投影同步，点击定位）
    ├── DiffPanel.tsx       版本选择 → diff 着色（added 绿/changed 黄/removed 列表红）
    │                       + old→new 列表 + 点击定位
    ├── Toolbar.tsx         复位视角/剖切/测量/Diff/隐藏/隔离/X-Ray/重置/下载
    ├── VisibilityToolbar.tsx / SectionControl.tsx / useMeasurements.ts
    ├── usePicking.ts       拾取 + 选中高亮
    ├── overrides.ts        EDITABLE_FIELDS 白名单 + applyOverrides 渲染合并
    └── store.ts            zustand：selectedId/tool/hiddenIds/overrides/changesVersion/
                            issues/diffOpen…
```

### 关键机制

- **选中链路**：`setSelected(id)` → usePicking 高亮 → PropertyPanel 显示 metadata 中该 GlobalId 的 pset
- **override 显示**：PropertyPanel 渲染时 `applyOverrides` 把 override 值覆盖在原值上并带修改标记；保存走 `PUT /api/models/{id}/entities/{entityId}/properties`
- **Diff 着色**：diff 返回的 guid 即 scene object id（metaObject id = GlobalId）；`entity.colorize = [r,g,b]`，清除时置 null；removed 在当前 XKT 无几何，仅列表呈现
- **自动刷新**：ViewerPage 持续 2s 轮询模型状态，ready→converting→ready 转换时 remount ViewerProvider 重载 XKT（外部 commit/AI 直改触发的重转也能捕获）

## 三、server（`viewer/server/`）

### 包结构

```
cmd/server/main.go        config（json + VIEWER_PG_DSN / VIEWER_EDIT_SERVICE_URL env）+ 依赖装配
internal/
├── api/                  全部 handler（api.go 核心 + edit.go 编辑编排），envelope {code,message,data}
├── store/                模型元数据/文件存储（仅文件实现）：Create/Get/List/SetStatus/Delete/Recover
├── convert/              转换队列：Runner 接口（ExecRunner 起 node 子进程）；
│                         Queue（2 worker、dedup、running/dirty 重跑、重启 Recover）
├── issue/  change/  override/   各 Store 接口 + FileStore + PgStore（构造时自动建表/ALTER）
└── editsvc/              edit-service HTTP 客户端（简单调用 10s / commit·diff 120s）
```

### 端点全表

| 路由 | 说明 |
| --- | --- |
| `POST /api/models` | 上传（multipart `file`，.ifc，MaxBytesReader 限大小）→ 入转换队列 |
| `GET /api/models` / `GET /api/models/{id}` | 列表（createdAt 倒序）/ 详情 |
| `POST /api/models/{id}/retry` | failed 重转 |
| `DELETE /api/models/{id}` | 级联删 issues/changes/overrides + 文件 |
| `GET /api/models/{id}/download` | 下载原 IFC |
| `GET /models/{id}/model.xkt` · `/metadata.json` | 静态产物（无 envelope） |
| `GET/POST /api/models/{id}/issues` · `PATCH/DELETE .../issues/{issueId}` | Issue CRUD（创建支持截图 ≤5MB） |
| `GET /models/{id}/issues/{file}` | Issue 截图（文件名白名单正则） |
| `GET /api/models/{id}/changes` | 修改记录（change log） |
| `GET /api/models/{id}/overrides` | `map[entityId]map[field]value` |
| `PUT /api/models/{id}/entities/{entityId}/properties` | override 写入（白名单五字段；每字段一条 change，operation=update） |
| `POST /api/models/{id}/overrides/migrate` | override → 真改迁移（见 ai-bim.md §4.4） |
| `PUT /api/models/{id}/edit/entities/{guid}` | 代理至 edit-service（provenance 先校验，非法 400 不发请求） |
| `GET/DELETE /api/models/{id}/edit/pending` · `GET .../edit/history` · `GET .../edit/versions` · `POST .../edit/diff` | 代理透传 |
| `POST /api/models/{id}/edit/commit` | 编排：Python commit → change log 展开（operation + IfcDiff 补充 diff）→ 重转 → `{committed, entries, reconverting}`；change log 失败降级 `warning` 不 500 |

错误映射：Python 404→404 / 409→409 / 422→400 / 其他→502。id 校验 `^m_[0-9a-f]{16}$`（路径穿越防护，与 Python 侧同规则）。

### 存储双实现

- 三个领域 store（issue/change/override）各有 `Store` 接口 + FileStore（`models/{id}/*.json`，tmp+rename 原子写）+ PgStore（pgx/v5，构造时建表/幂等 ALTER）
- 切换：`server_config.json` 的 `pgDSN` 或 env `VIEWER_PG_DSN`；不配置即 File 模式，零依赖可跑
- change.Entry：`{id, entityId, entityName, field, oldValue, newValue, author, provenance{source}, operation, diff, createdAt}`；operation 空串读取归一化为 `update`（兼容存量）
- 模型文件本身始终文件存储（`store` 包无 PG 实现）

## 四、converter（`viewer/converter/`）

- CLI：`node convert.js <input.ifc> <outDir>` → 写 `model.xkt` + `metadata.json`，stdout 打 `{"ok":true,...}`
- `lib/metadata.js`：web-ifc 遍历空间结构，metaObject id = IFC GlobalId（fallback `e<expressID>`），pset 合成 id `pset_<expressID>_<n>`；convert.js 有实体 id 与 metaModel id 一致性校验
- 重转触发：上传、retry、commit 编排、override 迁移（经 Go 队列；队列对运行中的同 id 任务做 dirty 重跑，保证最新 IFC 内容最终一定被转换）
- 测试：`npm test`（node:test，fixture `test/fixtures/wall-with-opening-and-window.ifc`）

## 五、edit-service（`viewer/edit-service/`）

```
app/
├── config.py        VIEWER_DATA_DIR（须与 Go dataDir 同目录）、EDIT_SERVICE_PORT(8100)
├── main.py          create_app()；/health；挂 routes_edits / routes_diff
├── registry.py      ModelRegistry：load（路径缓存同对象）/ save（tmp+os.replace 原子写，持锁）
│                    / lock（每路径一把锁）/ unload
├── routes_edits.py  PUT entities/{guid}（校验原子：全过才应用）/ pending GET·DELETE
│                    / commit（可选 body {operation: update|migrate}）/ history
├── routes_diff.py   GET versions / POST diff（快照间结果缓存）
├── versions.py      版本快照：首次 commit 前存 v1（原上传），每次 commit 存 v{n+1}
├── diffing.py       IfcDiff 适配层：added/removed 集合 + changed 门控 → get_info/get_psets 算 old/new
└── history.py       edit-history.json（原子写；记录真原值 oldValue）
```

端点详见 `docs/internal/ai-integration.md` 与 `docs/site/public/ai-tools.openapi.json`（`uv run python scripts/export_openapi.py` 再生成）。

注意：`VIEWER_DATA_DIR` 必须与 Go `dataDir` 指向**同一目录**（edit-service 按 `{dataDir}/uploads/{id}.ifc` 解析模型）。

## 六、数据布局（`viewer/data/`）

```
uploads/{id}.ifc                  原始上传（edit-service 的编辑对象）
models/{id}/
├── model.json                    模型清单（id/name/size/status/createdAt/error）
├── model.xkt / metadata.json     converter 产物
├── overrides.json / changes.json / issues.json   File 模式三 store
├── issues/i_*.png                Issue 截图
├── edit-history.json             edit-service 编辑史（真原值）
└── versions/                     v1.ifc, v2.ifc… + diff-{base}-{target}.json 缓存
```

## 七、测试与验证体系

| 层 | 命令 | 覆盖 |
| --- | --- | --- |
| Go | `cd viewer/server && go test ./...` | api（httptest 假 Python 服务验编排）、三 store File/PG（PG 需 `VIEWER_TEST_PG_DSN`，否则 skip）、队列（fake Runner：dedup/dirty 重跑/Recover）；`-race` 常开 |
| Python | `cd viewer/edit-service && uv run pytest` | registry（缓存/原子写/锁）、编辑（校验原子性/pending/commit/真原值/重启持久化）、版本快照、diff（增删改/缓存/错误路径） |
| web | `cd viewer/web && npm test`（+ build + lint） | client、store、各面板组件（mock xeokit）、DiffPanel 着色断言、ViewerPage 轮询重载 |
| converter | `cd viewer/converter && npm test` | 转换管线 + id 一致性 |
| 端到端 | `viewer/scripts/smoke.sh` | 上传→转换→下载→Issue CRUD→override/changes→edit-flow（PUT→pending→commit→change log→重转 ready→diff 含实体）；edit-flow 段在 edit-service 不可达时自动 skip |
| 真机 | 浏览器手动/自动化 | N+1 钉位验证、N+2 Diff Viewer 着色 + old→new 列表、AI REST 直连全流程 |

## 八、已知限制（维护者必读）

1. pending 在 edit-service 内存，重启丢失（README/AI 文档已声明）
2. AI 直连 Python 的 commit 不触发 Go 编排（change log/重转）；完整链路走 Go 代理
3. edit-service 的 versions/history/diff 缓存仅文件存储，与 File/PG 模式无关
4. diff 属性级（几何 diff 未做）；大模型 diff 无超时
5. ~~ifcdiff 本地 editable 依赖~~——**已解决（2026-08）**：`ifcopenshell`/`ifcdiff` 改为 PyPI 官方发布，`uv sync` 直接安装（skill 侧 `ifcquery` 随 `skills/aiifc/requirements.txt`）
