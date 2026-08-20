# 现状核对：dxf/ifc 存储规范 + agent 附加产物落盘调查计划

> 阶段定位：交付对齐（`agent_delivery_alignment.md`）的前置调查。
> **本阶段约束（重要）**：只考虑**正确交付**——每个产物的落盘规范（路径 / 格式 / 版本管理逻辑）要搞清楚；
> **不管流程怎么串通**（agent 工具怎么编排、skill 流程怎么走、上下文怎么喂）——流程串通是后续阶段再考虑。
> 先回答「东西该放哪、怎么存、怎么版本化」，再回答「怎么串起来」。
> 调查执行记录：step 1（服务端布局）✅ 2026-08-20，结果见 §6。
> 补充调查：render.json 定位 ✅（纯前端预览数据源，skill 不产出、agent 不消费；模型自检靠文本报告（geom_check/readback），shot.svg 是人的视觉返图（P-4 已砍前端透出））。
> 补充调查：项目/共享 ID 现状 ✅ 2026-08-20，结果见 §7。
> 执行记录：step 2（版本管理逻辑精读）✅ 2026-08-20，增量见 §6.6。
> 执行记录：step 3（store 层）✅ 2026-08-20，结果见 §9。
> 执行记录：step 4（附加产物盘点）✅ 2026-08-20，结果见 §10。
> 执行记录：step 5（skill CLI 工作区 + 沙箱共享）✅ 2026-08-20，结果见 §11。
> 执行记录：step 6（收敛对照表）✅ 2026-08-20，结果见 §12。调查完成。

## 0. 调查目标

1. 摸清 **IFC 与 DXF 各自的存储规范**——重点：版本管理逻辑（大版本 lockstep / 快照剪枝 / 回滚 / 列表语义）。
2. 摸清 **agent 运行的附加产物该落盘到哪里**——plan.json / bim_supplement.json / building.json / derived/ / skeleton/ / rooms.json / shot.svg / render.json / model.xkt / current.map.json 等，各自的归属（模型级 / 版本级 / 产物级）、读写方、格式契约。
3. 产出「存储规范对照表」：IFC vs DXF 逐项对比 + 附加产物归属结论，供后续交付对齐实施引用。

## 1. 调查问题清单

### A 块：dxf/ifc 存储规范（版本管理逻辑为重点）

| # | 问题 | 关键落点 |
|---|---|---|
| A1 | IFC 模型的文件布局全貌（uploads / models / scripts / versions / staging）？ | `services/ifc/app/routes_scripts.py` · `script_runner.py` · `script_staging.py` · `script_versions.py` · `server/internal/store/store.go` |
| A2 | DXF 模型的文件布局全貌？与 IFC 的同构/差异点？ | `services/cad/app/` 同族文件 |
| A3 | **大版本 lockstep 机制**：save 时哪些文件同 n 落盘？sidecar（meta/map）怎么配对？ | `script_versions.save()`（cad 与 ifc 各自的） |
| A4 | **快照剪枝**：旧 DXF/IFC 快照什么时候删、保留哪版？（可重建判定） | `_prune_rebuildable_snapshots` |
| A5 | **回滚语义**：rollback 恢复哪些文件？（script + 快照 + sidecar？） | `POST /script/rollback` 处理 |
| A6 | **versions 列表语义**：列出什么？（materialized 快照 + 脚本 + sidecar 清单？） | `GET /versions` |
| A7 | staging 缓冲：脚本暂存的持久化位置与恢复逻辑？ | `script_staging.py` |
| A8 | 当前产物（uploads/{id}.dxf / .ifc）与 current.map.json / render.json 的关系？ | `routes_scripts.py` run 语义 · `routes_render.py` |
| A9 | store 层元数据（Model.Kind / Size / Status）与文件布局的关系？ | `server/internal/store/store.go` |
| A10 | 沙箱执行环境（bwrap 挂载、工作目录、产物写出）对落盘的约束？ | `script_runner.py`（ifc/cad）`_sandbox_cmd` |

### B 块：agent 附加产物落盘归属

| # | 产物 | 问题 |
|---|---|---|
| B1 | `plan.json` | 语义（aiplan 任务书，只读输入）→ 落模型级 context？谁写（aiplan CLI / agent 工具）？格式契约（plan.schema.json）？ |
| B2 | `bim_supplement.json` | 同上（BIM 补充，对接 bim）？ |
| B3 | `building.json` | 语义（aidxf 交付 BIM 接口，floors + checksums）→ 落版本级 sidecar？谁写（aidxfv3 deliver CLI）？格式契约（building.schema.json）？ |
| B4 | `derived/` `skeleton.json` `rooms.json`（S0-S3 中间产物） | 是过程态（可重建）还是交付态？该不该进版本体系？ |
| B5 | `shot.svg`（前端预览载体） | 产物级？随渲染管线？ |
| B6 | `render.json` | 现有渲染契约（只读直挂），与交付链路关系？ |
| B7 | `model.xkt` | 转换产物（xeokit），现有 notify 管线谁写？ |
| B8 | `current.map.json` / `v{n}.map.json` | 现有 sidecar 先例——附加 JSON 版本化的现成模式？ |
| B9 | skill CLI 工作区（execute 落盘点） | 当前 aidxfv3/aiplan 命令的 `--out`/`--project` 写哪？与 models/{id}/ 的关系？ |
| B10 | 模型级 context（`models/{id}/context/`） | 该不该建？谁读写？与 plan/bim_supplement 语义的匹配？ |

## 2. 调查步骤（顺序执行，每步收敛一个小结论）

1. **step 1：服务端布局**——通读 `services/cad/app/` 与 `services/ifc/app/` 的存储相关文件（routes_scripts / script_runner / script_staging / script_versions / config），画出两张文件布局图（ifc / dxf），标注每个路径的写入方、读取方、生命周期。→ 回答 A1/A2/A8/A10。
2. **step 2：版本管理逻辑**——重点精读 `script_versions.py`（ifc 与 cad 各一）：save 的 lockstep 配对、sidecar 规则、剪枝条件、versions 列表、rollback 恢复面。→ 回答 A3-A6（产出版本管理逻辑表）。
3. **step 3：store 层**——读 `server/internal/store/store.go`：Model 元数据字段、CreateWithKind、SourcePath、目录约定。→ 回答 A9。
4. **step 4：附加产物盘点**——从 skill（aiplan/aidxf/aiifc）SKILL.md + steps + references/schemas 收集全部产物清单（名称/格式/schema），对照服务端布局找各自落点；标记「已有归属」vs「体系外」。→ 回答 B1-B8。
5. **step 5：skill CLI 工作区**——读 aidxfv3 CLI 与 aiplan CLI 的 `--out`/`--project`/落盘代码（`skills/aidxfv/v3/scripts/aidxfv3/`、aiplan_tools），确认 execute 当前写哪。→ 回答 B9。
6. **step 6：收敛**——汇总成「存储规范对照表」（IFC vs DXF 逐项 + 附加产物归属结论），标注哪些是现状事实、哪些是待裁决（如 context 目录）。

## 3. 产出交付物

1. **存储规范对照表**（IFC vs DXF）：布局 / lockstep / 剪枝 / 回滚 / 列表 / staging / 当前产物，逐项对照。
2. **附加产物归属表**：每个产物 → 落盘路径（现状/建议）/ 读写方 / 格式契约 / 是否进版本体系。
3. **待裁决点清单**：调查中发现的歧义（如 context 目录建不建、中间产物进不进版本）——只列问题与选项，**裁决留给实施阶段**。
4. 结论回写：把确认的存储事实回填 `agent_delivery_alignment.md` §4（修正/细化挂载方案）。

## 4. 验收标准

- 能回答 A 块全部 10 问（每问有文件/行级证据）。
- 能回答 B 块全部 10 问（每产物有落点结论或「待裁决」标记）。
- 对照表覆盖 ifc 与 cad 的逐项差异（不允许「大概一样」——差异点要列出来）。
- 不涉及流程串通设计（本阶段禁止：不设计 agent 工具怎么调、不设计编排顺序）。

## 5. 边界（不做）

- 不设计交付流程编排（用户约束：先正确交付，流程后置）。
- 不改代码（纯调查 + 文档）。
- 不碰前端契约（SSE/REST 7 路由不变）。

---

## 6. step 1 调查结果：服务端文件布局（2026-08-20 ✅）

> 依据文件：`services/{ifc,cad}/app/{route_common,config,versions,script_versions,script_staging,routes_scripts,script_runner,routes_render}.py`。
> `{DATA}` = `VIEWER_DATA_DIR`（两服务同目录约定）。两服务**逐文件同构**（ifc 的 registry/pending 在 cad 是模块级锁 map，差异见 6.4）。

### 6.1 公共布局（ifc/cad 一致，扩展名按 kind 区分）

```
{DATA}/
├── uploads/{id}.ifc|.dxf        ← 当前产物（模型上传原文；run 沙箱原子替换为最新 run 结果）
└── models/{id}/
    ├── scripts/v{n}.py          ← 大版本构建脚本（**单一事实源**）
    ├── scripts/v{n}.meta.json   ← 版本元数据 sidecar（{version, note, savedAt}）
    ├── scripts/v{n}.map.json    ← ScriptMap sidecar（XDATA 定位表；save 时随 lockstep 落，可空）
    ├── versions/v{n}.ifc|.dxf   ← 产物快照（**仅最新版物化**；旧版有脚本即剪枝/懒物化）
    ├── {ifc_cache|dxf_cache}/v{n}.ifc|.dxf ← 历史版懒物化缓存（LRU≤4，非状态，可重建）
    ├── current.map.json         ← 当前 run 的 ScriptMap 信封 {"scriptHash", "map"}（run 写、locate/edit-call 读）
    ├── render.json              ← 渲染 payload（run/save 钩子原子写；前端 GET /render.json 直读）
    ├── script_staging.json      ← 暂存缓冲持久化（WPS undo/redo，MAX_STEPS=10；重启恢复）
    └── bootstrap.ifc|.dxf       ← 首次暂存脚本时保留的上传原件（plain→script-backed 迁移锚点）
```

### 6.2 路径写方/读方/生命周期表

| 路径 | 写方 | 读方 | 生命周期 |
|---|---|---|---|
| `uploads/{id}.ifc\|.dxf` | 上传（store/Go）；`run`/`save`/`rollback` 沙箱原子替换（tmp+replace） | script 端点校验存在；diff/staging 基线 | 模型存活期；无版本（当前态） |
| `models/{id}/scripts/v{n}.py` | `save`（script_versions.save，原子） | `GET /script`（seed base）；`rollback`；`diff`；懒物化 | 永存（单一事实源） |
| `scripts/v{n}.meta.json` | `save` 同步 | `GET /scripts`（note 列表） | 永存，与 v{n}.py lockstep |
| `scripts/v{n}.map.json` | `save` 同步（map_text 可空） | 定位/改参（locate/edit-call 的版本侧） | 永存，与 v{n}.py lockstep |
| `versions/v{n}.ifc\|.dxf` | `save`（versions.snapshot_as，原子 copy） | `GET /versions`；materialize 命中 | **仅最新物化**：旧版有脚本 → `_prune_rebuildable_snapshots` 删除（可懒物化重建）；无脚本（迁移期 entity-edit）保留 |
| `{ifc_cache\|dxf_cache}/v{n}.*` | 懒物化（按需 sandbox 重建） | 历史版本请求 | LRU≤4（mtime 淘汰）；非状态，可随时重建 |
| `models/{id}/current.map.json` | `run`/`rollback`（script_runner map_out 信封） | `locate`/`edit-call`（scriptHash 比对判 stale） | 当前态；staging 变化即 stale |
| `models/{id}/render.json` | `run`/`save` 钩子（`_publish_render_json` 原子） | `GET /render.json`（直接读文件；损坏降级即时生成） | 当前态；生成失败删旧防错位 |
| `models/{id}/script_staging.json` | staging 每次 push/undo/redo/discard/save/reset（原子 tmp+replace） | StagingRegistry 懒加载恢复 | 暂存态；save 后清空（base=current） |
| `models/{id}/bootstrap.ifc\|.dxf` | 首次 stage 时 `_preserve_bootstrap`（原子 copy） | （迁移锚点） | 一次性；已有大版本/bootstrap 存在即跳过 |

### 6.3 版本管理逻辑（A3-A7 回答）

- **lockstep（A3）**：`script_versions.save()` 取 `n = max(next_script, next_dxf)`，同 n 落 `v{n}.py` + `v{n}.meta.json` + `v{n}.map.json`（可空）+ `versions/v{n}.dxf`。**sidecar（meta/map）挂 scripts/ 目录、随版本 lockstep——这是附加 JSON 版本化的现成模式**。
- **剪枝（A4）**：save 后 `_prune_rebuildable_snapshots` 删 `versions/v{m}`（m<n）**且有脚本**的快照；无脚本的快照（迁移期 entity-edit）保留。→ 旧产物不冗余，脚本可重建。
- **回滚（A5）**：`rollback` = 取 `scripts/v{n}.py` 全文 → staging.reset(base=script) → 沙箱 re-run 进 uploads。**只恢复脚本+产物，不恢复 map/meta sidecar**（sidecar 由 re-run 重建 current.map.json）。
- **列表（A6）**：`GET /versions` = versions/ 目录扫描（物化快照，最新 → current）；`GET /scripts` = scripts/ 目录 v{n}.py 扫描 + meta note。
- **staging（A7）**：`{id}/script_staging.json` 持久化（base/history[≤10]/cursor），StagingRegistry LRU(32) 懒加载；`save` 后 base=current、history 清空。
- **懒物化（A8 补充）**：历史版本按需 sandbox re-run 到 `{ifc|dxf}_cache/`（LRU≤4）；重建语义等价非字节等价（确定性 key 保证）。

### 6.4 ifc vs cad 差异点（A1/A2 对照）

| 差异 | services/ifc | services/cad |
|---|---|---|
| 锁 | `registry.py` ModelRegistry + pending（上传缓存失效面） | 模块级 `model_lock` LRU map（无 registry/pending） |
| 物化缓存 | `ifc_cache/`（uuid5 GlobalIds 语义等价） | `dxf_cache/`（cad_script_lib.reset_state 确定性 key） |
| 编辑面 | routes_edits（entity-edit 退役 410）+ routes_user_edits（diff/upload） | 无（纯 script-as-source） |
| 迁移期快照 | versions/ 可能有无脚本的 entity-edit 快照（不剪枝） | 无此状态（快照必有脚本配对） |
| 端点面 | 同构 script 全套（get/put/params/undo/redo/discard/run/save/scripts/rollback/diff/staging-diff/locate/edit-call） | 同构（+ diff 端点共用语义） |
| 产物扩展名 | `.ifc` | `.dxf` + render.json 直挂（ifc 侧 xeokit 走 model.xkt 转换链，render.json 语义不同） |

> **结论**：两服务存储规范**同构**——「script-as-source 版本体系」是统一范式；附加 JSON 产物的版本化挂载点 = `scripts/v{n}.xxx.json` sidecar（lockstep 先例：meta/map）。

### 6.5 对附加产物落盘的直接启示（B 块预判）

> ⚠️ 注：本节是 step 1 时的预判（「模型级 context」）——**已被 P-1 裁决推翻**（plan/bim_supplement 改挂方案级目录，见 §12.3.1）；保留作调查演进痕迹。

- **模型级当前态**（plan.json/bim_supplement.json 语义：只读输入/当前上下文）→ 自然挂 `models/{id}/context/`（新增子目录，与 current.map.json 同层；不进版本体系）。
- **版本级交付物**（building.json 语义：随交付迭代追溯）→ 挂 `scripts/v{n}.building.json` sidecar（lockstep 先例现成，`save()` 加可选参数即扩展）。
- **中间产物**（derived/、skeleton.json、rooms.json）→ 对照 6.3 剪枝纪律：凡脚本可重建的不落版本（对应 ifc_cache/dxf_cache 的「非状态缓存」模式）；**待裁决**（B4，见 §3 清单）。
- 读写方约束：所有落盘必须原子（tmp+os.replace）+ 模型锁；**服务端只认 `{DATA}/uploads` 与 `{DATA}/models/{id}` 两棵子树**——skill CLI 产物若落这两棵子树外（如 skill 工作区），服务端零认知。

## 7. 补充调查：项目/共享 ID 现状（2026-08-20 ✅）

> 背景：用户提出 CAD 与 BIM 之间应存在「整体共享 ID」——同一套 plan → 多 DXF → 由该 DXF 生成的 bim 需要共享 ID 贯穿。先摸清现状再设计。

### 7.1 平台侧 ID 现状（无 project 概念）

- **REST 只有 `/models` 资源**：`POST /api/v1/models`（上传）、`GET /models`、`GET /models/{id}`、`POST /models/{id}/retry`、`DELETE /models/{id}`、`GET /models/{id}/download`、只读 `model.xkt`/`metadata.json`/`render.json`（api.go:62-73）。
- **`POST /api/v1/chat/projects` 是伪项目**：仅创建**单个骨架模型**（`createProjectForAgent` → `skeletonProjectIFC` + `St.Create`），无 project 资源、无聚合概念。
- **store 层**：只有 `Model{ID, Name, Size, Kind, ...}`；ID = `m_[0-9a-f]{16}`（模型级）。**无项目/方案/设计实例级 ID**。
- **前端**：`/`（LibraryPage 模型库）+ `/view/:id`（查看器）——**没有项目页**；「项目名」只是模型 `name` 字符串（LibraryPage 的 projectName → createChatProject 仅命名骨架模型）。

### 7.2 skill 产物链 ID 现状（project 字段空语义）

| 产物 | 字段 | 现状 |
|---|---|---|
| `plan.json` | `project`（string，minLength:1，无 description） | 空语义（名称？目录？ID？） |
| `building.json` | `project`（同上）+ `floors[].dxf/sha256` + `checksums` | project 空语义；floors 索引各层 DXF + 哈希 |
| `bim_supplement.json` | `project` + `source_plan_sha256` | project 空语义；`source_plan_sha256` 是 plan **版本哈希追溯**（非 ID） |
| aidxfv3 CLI | `--project <dir>` | **工作区路径**，不是标识 |

### 7.3 结论（事实）

1. **当前平台无 projectId**：1 项目 ≈ 1 模型（前端同一项目页下就一个 id）。
2. **skill 无共享 ID**：三个 schema 的 `project` 均空语义；跨产物追溯只有 `bim_supplement.source_plan_sha256`（plan 哈希 → bim，**版本对齐非建筑对齐**）。
3. **未来形态（用户意图）**：1 project = 多套方案；同一套 = plan(1) → DXF(N) → bim(1)，需要**方案级共享 ID** 贯穿 plan/building/bim_supplement（也关联多个平台模型 modelId）。

### 7.4 对设计的启示（待裁决，不在此定案）

- 共享 ID 载体候选：`plan.json.project`（plan 是管线起点、一套方案的源头，plan → building → bim 天然共享）——但 `project` 语义要重新定义为「方案 ID」而非名称。
- building.json 作为交付索引，`project` 字段填共享 ID，`floors[].dxf` 指向各楼层 DXF（结合 §6 布局：模型级 context 或版本级 sidecar 挂载）。
  > ⚠️ 注：本节是补充调查时的预判——**已被 P-1 裁决更新**（building.json 版本级 sidecar 不变；plan 挂方案级目录，见 §12.3.1）。
- 当前阶段（单模型单 ID）不必引入 projectId 资源；先让 skill 产物链的 `project` 字段语义落地（方案 ID），平台 projectId 迁移留后续。

## 8. step 2 调查结果：版本管理逻辑精读（2026-08-20 ✅）

> 增量：补齐 materialize 触发面、Go/agent 暴露面、rollback 完整恢复面、迁移态确认。
> 核心机制（lockstep/剪枝/sidecar）已在 §6.3——本节只列 step 2 新确认的事实。

### 8.1 版本管理逻辑表（A3-A6 完整回答）

| 机制 | 结论 | 证据 |
|---|---|---|
| lockstep（A3） | `save()` 取 `n=max(next_script, next_dxf)`；同 n 落 `scripts/v{n}.py` + `v{n}.meta.json` + `v{n}.map.json`(可空) + `versions/v{n}.{ifc\|dxf}` | script_versions.save()（ifc/cad 逐行一致，仅扩展名差异） |
| 剪枝（A4） | save 后删 `versions/v{m}`（m<n）**且有脚本**的快照；无脚本（ifc 迁移态 entity-edit）保留 | `_prune_rebuildable_snapshots`（ifc/cad 同） |
| 回滚（A5） | `rollback` = `load_script(v{n}.py)` → `staging.reset(base=script)` → 沙箱 **re-run 进 uploads**（`_run_into_uploads` 顺带重建 current.map.json + render.json）→ 返回 script。**meta/map sidecar 不恢复**（re-run 重建 current 态） | routes_scripts.py rollback_script（ifc/cad 同） |
| 列表（A6） | Python `/models/{id}/scripts` 返回 `{scripts:[{version,createdAt,note}], versions:[{version,createdAt}]}`（**组合**）；Python `/models/{id}/versions` 只列物化快照 + current | routes_scripts.py:585-610 |
| staging（A7） | `script_staging.json`（base/history[≤10]/cursor），StagingRegistry LRU(32) 懒加载持久化；save 后 base=current、清空 | script_staging.py |

### 8.2 新确认事实（step 2 增量）

1. **materialize 触发面**：`materialize_version` 只在 **/diff 端点**触发（`routes_diff.py:72`（cad）/`:65`（ifc））——对历史版本做 diff 时，若快照被剪枝 → 查 cache → 无则沙箱重建到 cache。顺序：`versions/v{n}` 快照 → `{ifc|dxf}_cache/v{n}`（命中刷新 mtime）→ sandbox re-run。
2. **Go/agent 暴露面**：Go 只代理 `GET /api/v1/models/{id}/scripts`（script.go:31，透传 Python 组合响应）；**`/versions` 不代理**（Python 内部端点，无 Go 路由）。agent `get_versions` 工具走 `/models/{id}/scripts`（tools.go:301）。
3. **rollback 完整恢复面**：只恢复「脚本 + 当前产物（uploads + current.map.json + render.json）」，**不恢复** meta/map sidecar（它们仍留在原 `scripts/v{n}.meta.json` 历史版上，不回写 staging）。——与「回滚后 sidecar 随 re-run 重建」一致。
4. **迁移态确认**：ifc `routes_edits.py` 全部端点 **410 Gone**（entity-edit 退役）；「无脚本的 versions 快照」是理论迁移态（不可达），cad 无此状态（快照必有脚本配对）。
5. **versions 列表的 current 语义**：Python `/versions` 取 `listed[-1]` 为 current（物化快照最后一个），非「最新大版本」语义——被剪枝的历史版不在其中（要去 `/scripts` 看全量脚本）。

### 8.3 对附加产物 sidecar 的版本化含义

- **building.json sidecar 的自然实现**：在 `script_versions.save()` 加可选参数（如 `sidecars: dict[str,str]`），同 n 落 `scripts/v{n}.building.json`——与 map.json 完全同模式；剪枝/回滚语义自动一致（sidecar 永存于 scripts/，不受快照剪枝影响）。
- **注意**：rollback 不恢复 sidecar → 若 building.json 是「交付索引」且消费方要按版本追溯，它挂在 scripts/ 下天然随版本永存（✓）；若消费方要「当前态」，需另建方案级目录引用（§12.3.1，plan 走方案级，building 当前态可另议）。

## 9. step 3 调查结果：store 层（Go，2026-08-20 ✅）

> 依据：`server/internal/store/store.go`（212 行全读）。A9 回答。

### 9.1 Model 元数据

```go
type Model struct {
    ID        string    // m_[0-9a-f]{16}（crypto/rand）
    Name      string    // 展示名（「项目名」只是它）
    Size      int64
    Status    string    // converting | ready | failed
    Kind      string    // ifc | dxf（空 = 存量迁移按 ifc）
    CreatedAt time.Time
    Error     string
}
```

- **无 project/方案/分组字段**——加 projectId 需扩展 model.json（迁移兼容：无字段视为未分组）。
- 元数据落 `models/{id}/model.json`（原子 tmp+rename）。

### 9.2 目录约定与生命周期

| 路径 | 归属 | 生命周期 |
|---|---|---|
| `{DATA}/uploads/{id}.ifc\|.dxf` | Go store 创建（CreateWithKind 落上传源）；**Python 服务也写同一路径**（run/save 原子替换） | 模型存活期 |
| `{DATA}/models/{id}/model.json` | Go store 唯一写者 | 同上 |
| `{DATA}/models/{id}/scripts\|versions\|staging\|render\|map\|cache` | Python 服务写 | 同上 |
| `{DATA}/models/{id}/` 全目录 | **Go Delete 整个 `os.RemoveAll(ModelDir)`** | 模型删除即全清 |

### 9.3 关键事实（A9）

1. **models/{id}/ 是模型私有空间、双写者共存**：Go 管 `model.json`，Python 管 `scripts/versions/staging/render/map/cache`——**无冲突协议**（各写各的文件名，天然分区）。→ 新增 `context/`、`deliver/` 子目录同样落入此空间，双写者纪律延续（Go 或 Python 谁写谁管，不互相覆盖）。
2. **Delete 即全清**：任何挂 `models/{id}/` 下的附加产物随模型删除继承生命周期——context/、deliver/、scripts/v{n}.building.json 都不需要单独清理逻辑。
3. **CreateWithKind 语义**：ifc status=converting（等转换队列）；dxf status=ready（无 XKT 转换，W-0040）。
   > ⚠️ 注：2026-08-20 组织逻辑澄清——create_project **空白化**（通用项目容器，无 kind 语义）；模型由构建过程产生，create_project 不产模型。
4. **Recover**：重启时 converting → failed（不阻塞启动）。
5. **List**：扫 `models/` 目录 + 读各自 model.json，按 CreatedAt 倒序——**无分组/过滤**（若未来 projectId，List 需扩展）。

### 9.4 对交付对齐的含义

- **create_project 空白化**（A1 回改方向）：通用项目容器（无 kind 语义、不产骨架模型）——「kind=dxf 骨架脚本」是围绕上传模型的旧组织逻辑残留，废弃（2026-08-20 澄清）。
- **附加产物归属**：context/（模型级）、deliver/（多文件交付）天然继承 `models/{id}/` 生命周期——Delete 自动清理，无需新逻辑。
- **共享 ID 载体**：Model 无字段 → 若加 projectId 走 model.json 扩展（兼容空值），或由 skill 产物链的 `project` 字段承担（§7.4，先不引入平台字段）。

## 10. step 4 调查结果：skill 附加产物盘点（2026-08-20 ✅）

> 依据：`skills/dist/{aiplan,aidxf,aiifc}` 的 SKILL.md + steps + references。B1-B8 回答。
> **重要：aidxf 交付形态已 v2**——building.json = 单一交付物（plan 形态整栋楼 + 逐 zone DXF 指针），schema 已同步。

### 10.1 产物总清单（对照现有体系分类）

**① 已有归属（服务端已认知）**

| 产物 | 归属 | 说明 |
|---|---|---|
| 构建脚本（ifc/cad） | staging → `scripts/v{n}.py` 大版本 | 单一事实源（aiifc/aiplan 契约脚本） |
| 产物文件（ifc/dxf） | `uploads/{id}.ifc\|.dxf` + `versions/v{n}` | run/save/rollback 全链路 |

**② 方案级目录（B1/B2，P-1 已裁决——原「模型级 context」预判被推翻）**

| 产物 | 来源 | schema | 落点建议 |
|---|---|---|---|
| `plan.json` | aiplan（P0-P4 落盘 `{workspace}/plan/`） | plan.schema.json | `{DATA}/plans/{projectID}/plan.json`（方案级 + 方案级版本化） |
| `bim_supplement.json` | aiplan（双轨落盘） | bim_supplement.schema.json | `{DATA}/plans/{projectID}/bim_supplement.json` |

**③ 体系外 → 版本级 sidecar 候选（B3，交付物追溯语义）**

| 产物 | 来源 | schema | 落点建议 |
|---|---|---|---|
| `building.json`（v2） | aidxf `deliver` | building.schema.json（zones + dxf/sha256） | `scripts/v{n}.building.json`（随 save lockstep，§8.3 模式） |

**④ 中间/过程态（B4/B5，可重建、非交付物）**

| 产物 | 来源 | 性质 | 处置 |
|---|---|---|---|
| `derived/`（floors.json + zone 包 + skeleton_base.json） | aidxf S0 preprocess | 可重建（plan → preprocess 重跑） | 不进版本体系；留 skill 工作区（对应 §6.3 剪枝纪律） |
| `skeleton.json` | aidxf S1 | 可重建（含断点确认输入） | 同上 |
| `missions/<zone>.*/`（rooms.json + floor.dxf + shot.svg + geom_check.json + mission.json） | aidxf S2-S3 | 过程态（zone 级工作区） | 同上；`<zone>.rooms.json` v2 明确留 missions/ |
| `readback.json` / `reconcile` | aidxf 对账 | 过程态 | 同上 |
| `features.json` + design JSON draft | aiifc（辅助规划） | 非交付物 | 同上 |
| `design_review.py` 报告 | aiifc 黑盒检查 | 文本报告 | 报告进工具结果（文本），不落模型 |

**⑤ 前端可见产物（B5-B7，现有链路）**

| 产物 | 来源 | 消费 | 现状 |
|---|---|---|---|
| `render.json` | services/cad 派生（run/save 钩子） | 前端 Canvas | ✅ 已有（§6.1） |
| `model.xkt` | converter 转换（ifc notify 管线） | 前端 xeokit | ✅ 已有（§6.4 差异） |
| `shot.svg` | aidxf `svg` 命令（zone 建造段） | 人的视觉返图（P-4 已砍前端透出） | 留 skill 工作区，不进服务端 |

### 10.2 关键确认（B 块回答）

- **B1/B2**：plan.json / bim_supplement.json = aiplan 双轨产物，`project` 字段（§7.2）→ 模型级 context 候选，消费方：cad/bim 下游。
- **B3**：building.json **v2 已按用户意图设计**——「plan 形态整栋楼 + 逐 zone DXF 指针（dxf/sha256/floors_from/to）」，几何细节留 DXF。→ 版本级 sidecar 候选（随 save lockstep，§8.3 模式现成）。
- **B4**：derived/skeleton/missions/rooms 全为**可重建过程态**——不进版本体系（与剪枝纪律一致：脚本可重建的不落版本）；`missions/` 是 skill 工作区，服务端零认知（§6.5）。
- **B5**：shot.svg 是 skill 产出的视觉返图（zone 级）——**P-4 已裁决砍前端透出**（render.json 才是服务端管的预览物）；留 skill 工作区备查，模型自检靠文本链。
- **B6/B7**：render.json（cad 派生）、model.xkt（ifc 转换）均为现有链路，与 skill 无直接关系。
- **B8**：`scripts/v{n}.map.json` 是现成 sidecar 模式（lockstep + 剪枝免疫）——building.json 版本化完全对齐它。

### 10.3 对落盘设计的汇总（结合 §6/§8/§9）

```
方案级目录（P-1 已裁决）：           {DATA}/plans/{projectID}/plan.json + bim_supplement.json（方案级版本化）
版本级 sidecar（随 save lockstep）：  scripts/v{n}.building.json（P-2：内容源 = 服务端读 CLI 文件）
中间过程态（不进版本）：              skill 工作区（derived/、missions/、skeleton.json）
交付主产物：                          uploads/{id}.dxf + versions/v{n}.dxf（现有链路）
前端可见：                            render.json（服务端）· model.xkt（ifc）· shot.svg（P-4 砍透出，留工作区）
生命周期：                            方案级目录独立于模型；模型侧挂 models/{id}/ 下 → Delete 自动全清（§9.2）
```

## 11. step 5 调查结果：skill CLI 工作区 + 沙箱共享（2026-08-20 ✅）

> 用户问题：skill CLI **最后构建交付 DXF 这一步能否和用户共享同一个沙箱环境**（像 ifc 那样）？
> 结论：**能——设计已声明（M4-① bwrap Operator，照抄 script_runner 沙箱参数），但尚未实现**；当前 execute 是裸 `/bin/sh -c`。

### 11.1 现状：两条执行路径，隔离不一致

| 路径 | 执行环境 | 沙箱 | 写盘目标 |
|---|---|---|---|
| **用户/agent 脚本**（`run_script`） | services/cad `script_runner.py` | ✅ **bwrap**：`_runtime_ro_binds`（系统库）+ `--ro-bind flows_dir` + `--tmpfs /tmp` + `--dev /dev` + `--proc /proc` + `--bind workdir` + `--unshare-net` + `--die-with-parent`；**不挂 /data、/etc**（`_sandbox_cmd`，237-255 行；detect_backend 159 行） | `uploads/{id}.dxf`（原子） |
| **skill CLI**（`execute`） | 官方 local backend `/bin/sh -c`（fs_backend.go:12） | ❌ **无 bwrap**（仅 `validateSkillCommand` 白名单 aiplan/aidxfv3） | skill 工作区（命令自身落盘，fs_backend.go:15） |

### 11.2 设计声明（有，未实现）

| 声明 | 内容 | 状态 |
|---|---|---|
| **M4-① bwrap Operator**（agent_deployment_plan.md:402） | 自实现 `filesystem.Shell`/`StreamingShell` 接口（**路径 jail + bwrap，参数照抄 script_runner.py:159-172**）——**替代 local 裸 `/bin/sh -c`，作为 filesystem middleware 的 StreamingShell** | ⏳ 未做 |
| **M2-② 持久工作区沙箱**（:390） | bwrap bind `models/{id}/pipeline/`（plan 产物 `{workspace}/plan/` 同区） | ⏳ 未做 |
| D12 更强隔离 | 「更强隔离（bwrap 路径 jail + unshare-net）挂 `filesystem.Shell` 接口后」 | ⏳ 未做 |

### 11.3 回答用户问题（能否共享同一沙箱）

- **能**：实现 M4-① 后，skill CLI 的 execute（含 `aidxfv3 deliver`/逐 zone 画 DXF）走**同一个 bwrap 沙箱模式**（照抄 script_runner 参数）——系统库 ro-bind + tmpfs /tmp + unshare-net + workdir bind，与用户 run_script 的沙箱同参数、同纪律。
- **和 ifc 的对应关系**：ifc 侧用户 run_script 与 agent 脚本本来就共用 services/ifc script_runner bwrap（单沙箱）；cad 侧现状是 **agent 的 skill CLI 游离沙箱外**（裸 sh -c），M4-① 就是补这个洞——让 agent 的 CLI 也进沙箱。
- **注意点（M4-① 路径 jail 细节）**：
  - script_runner 沙箱**不挂 /data**（用户脚本不碰其他模型）——skill CLI 沙箱若需读 `plan.json`（models/{id}/context）或写 `models/{id}/pipeline/`，需**白名单 bind 对应模型子目录**（非全挂 /data）。
  - skill CLI 产物目前落 skill 工作区；进沙箱后应写 **workdir bind 的模型子树**（对齐 M2-② `models/{id}/pipeline/`），产物即落服务端认知区（接 §10 落点）。
  - 白名单（`validateSkillCommand`）与沙箱**双层防线**：先命令白名单，再 bwrap 路径 jail——不冲突，M4-① 保留现有白名单。

### 11.4 对交付对齐的含义

> ⚠️ 注：本节原按「中间产物也要落服务端认知区」推导——**已被 P-5 裁决修正**：中间流程走 execute 自由探索（产物为 run_script 输入），**只有交付级产物**（最终 DXF/plan/building）经 run_script 落规范位置。

- **「skill CLI 交付 DXF 进沙箱」= 交付级 run_script 化**（P-5 已裁决）：最终交付脚本（cad_script_lib 契约）在用户共享沙箱执行 → DXF 进 uploads + building.json 同期落盘（接 §10.3）。中间 S0-S4（preprocess/normalize/check/rooms）继续 execute 自由探索，无需沙箱化。
- **依赖序（修正后）**：交付脚本形态（cad_script_lib 契约 / aiplan land 落盘脚本）→ 服务端 run_script 支持非几何产物（plan JSON 落方案级目录）→ 交付对齐 P 系列可落。M4-① bwrap Shell 不再是前置（execute 中间流程保持现状，交付级复用现有 script_runner 沙箱）。

## 12. step 6 调查结果：存储规范收敛对照表（2026-08-20 ✅）

> 调查完成。本节 = 全部 step 的收敛：IFC vs DXF 逐项对照 + 附加产物归属结论 + 待裁决点。

### 12.1 IFC vs DXF 存储规范对照表（A 块收敛）

| 维度 | IFC | DXF | 同构 |
|---|---|---|---|
| 当前产物 | `uploads/{id}.ifc` | `uploads/{id}.dxf` | ✅ 同构 |
| 脚本事实源 | `scripts/v{n}.py` | 同 | ✅ 同构 |
| 大版本 lockstep | `n=max(script,ifc)`，`v{n}.py`+`meta.json`+`map.json`+`versions/v{n}.ifc` | 同（dxf） | ✅ 同构（扩展名差异） |
| 快照剪枝 | 旧版有脚本即删（可重建） | 同 | ✅ 同构 |
| 懒物化 | `ifc_cache/`（LRU≤4，/diff 触发） | `dxf_cache/`（LRU≤4，/diff 触发） | ✅ 同构 |
| 回滚 | 脚本 + re-run；sidecar 不恢复 | 同 | ✅ 同构 |
| staging | `script_staging.json`（10 步） | 同 | ✅ 同构 |
| bootstrap | `bootstrap.ifc`（首暂存保留原件） | `bootstrap.dxf` | ✅ 同构 |
| 渲染链 | `model.xkt`（converter 异步转换，notify 管线） | `render.json`（服务端派生，run/save 钩子直写） | ❌ **异构** |
| 第二编辑面 | routes_edits 全 410（退役）+ routes_user_edits | 无（纯 script-as-source） | ❌ 差异 |
| 锁/注册 | registry.py ModelRegistry + pending | 模块级 model_lock LRU | ❌ 差异（实现） |
| 迁移态快照 | versions/ 可能有无脚本快照（不剪枝） | 无此状态 | ❌ 差异 |
| store 元数据 | `Model{ID,Name,Size,Status,Kind,CreatedAt}`（无项目字段） | 同 | ✅ 同构 |

**结论**：存储骨架与版本管理逻辑**逐项同构**（唯一结构性差异 = 渲染链：xkt vs render.json）；附加产物的挂载方案无需区分 kind，一套模式双 kind 复用。

### 12.2 附加产物归属收敛表（B 块收敛）

| 产物 | 现状 | 归属结论 | 状态 |
|---|---|---|---|
| `plan.json` | 体系外（skill 工作区） | 方案级目录：`{DATA}/plans/{projectID}/plan.json`（方案级版本化） | **已裁决**（P-1） |
| `bim_supplement.json` | 体系外 | 方案级目录：`{DATA}/plans/{projectID}/bim_supplement.json` | 已裁决（P-1） |
| `building.json`（v2） | 体系外 | 版本级 sidecar：`scripts/v{n}.building.json`（对齐 map.json） | **已裁决**（D13） |
| derived/ skeleton/ missions/ | 体系外 | 过程态，不进版本（留 skill 工作区；可重建） | **已裁决**（剪枝纪律） |
| shot.svg | 体系外 | 人的视觉返图，留 skill 工作区 | **已裁决**（P-4 砍前端透出） |
| render.json / model.xkt | 已有链路 | 不动 | — |
| skill CLI 中间产物（S0-S4） | skill 工作区（execute 自由探索） | 交付级输入工作区（run_script 时 bind）；最终产物经 run_script 落规范位置 | **已裁决**（P-5） |

### 12.3 待裁决点清单（调查发现，裁决留实施阶段）

| # | 待裁决 | 选项 | 关联 |
|---|---|---|---|
| P-1 | plan/bim_supplement 挂载 | **✅ 已裁决（2026-08-20）**：方案级目录 `{DATA}/plans/{projectID}/` + **方案级版本化**（plan 演化独立于模型版本，可追溯）——不挂模型 context、不挂模型版本 sidecar | 用户裁决 |
| P-2 | building.json sidecar 何时落（save 时从哪取内容） | **✅ 已裁决（2026-08-20）**：**run_script 同期产物**——交付脚本把 building.json 写沙箱 workdir，save 时服务端读（对齐 map_text 现有模式 routes_scripts.py:572-576；不存在则无 sidecar）。**不选 agent 工具传内容**——64KB 截断红线 + CLI 同源一致性 | §8.3 + P-5 |
| P-3 | 方案级共享 ID（projectID）载体 | **✅ 已裁决（2026-08-20）**：方案 ID 是方案级目录键（`{DATA}/plans/{projectID}/`）+ skill 产物链 `project` 字段（plan/building/bim_supplement 共享）；格式 `p_...` 待实施细化 | 用户裁决（平台 projectId 迁移后置） |
| P-4 | shot.svg 前端透出通道 | **✅ 已裁决（2026-08-20）**：**砍掉前端透出**。shot.svg 留 skill 工作区（模型 execute 生成，作为人的视觉返图备查）；不进服务端、不透出前端。模型自检靠文本链（geom_check/readback/validate）——svg 是 reconcile FAIL 的可选诊断（draw_composition.md:90），非模型可读图像（read_file 是 XML 文本） | 用户裁决 |
| P-5 | skill CLI 工作区落点（M2-② 细化） | **✅ 已裁决（2026-08-20）**：**交付级统一走用户共享 run_script 沙箱**（一人一个 run_script：plan/cad/ifc）；**中间流程走通用独立脚本**（execute 自由探索，产物为 run_script 输入工作区，不需落服务端认知区）。最终产物经 run_script 落规范位置（uploads / 方案级目录 / 版本 sidecar） | 用户裁决（三级执行模型：交付级沙箱 / 中间 execute） |
| P-6 | building.json 与 DXF 的交付粒度（成套） | ① 每 zone DXF 独立模型（模型族 + 索引）② 模型内多文件 deliver/ ③ 主模型+引用 | 用户：未来 1 project 多套（§7）——**当前阶段可不裁决**，先正确交付单套 |

### 12.3.1 方案级目录设计（P-1/P-3 已裁决，2026-08-20）

```
{DATA}/plans/{projectID}/          ← 方案 ID 是目录键（方案级存储，独立于模型）
├── plan.json                      ← 当前方案（盖写，原子 tmp+replace）
├── bim_supplement.json            ← 当前 BIM 补充（盖写，原子）
└── plan_history/                  ← 方案级版本化（plan 演化可追溯，格式实施细化）
    └── v{n}.json
```

- **层级**：方案（projectID）→ 管线产物（plan/bim_supplement/building）→ 模型族（DXF，现有模型版本体系）。
- **共享 ID 贯穿**：`plan.json.project` = `building.json.project` = `bim_supplement.json.project` = projectID——一套方案的全部产物以此对齐。
- **building.json** 仍挂**模型版本 sidecar**（随 cad 交付迭代，D13 不变）——交付索引随 DXF 走，plan 随方案走。
- **生命周期**：方案级目录独立于模型 Delete（一个方案可能多模型）；方案删除规则实施细化（孤儿方案？）。

### 12.4 调查结论回填（agent_delivery_alignment.md §4 修正点）

1. **D13 细化**：building.json 内容已按 v2 落地（plan 形态整栋楼 + 逐 zone DXF 指针，schema 已更新）——版本 sidecar 挂载不变；plan/bim_supplement 的 context 挂载为 **P-1 待裁决**。
2. **D14 细化**：create_project 空白化（通用项目容器，无 kind 语义）——2026-08-20 组织逻辑澄清（废弃「kind=dxf 骨架脚本」残留）。
3. **新增依赖**：交付对齐 P 系列前置 M2-②（工作区约定）+ M4-①（bwrap Shell），§11.4。
4. **共享 ID**：skill 产物链 `project` 字段语义空洞 → 定义方案 ID（P-3 待裁决），当前不引入平台 projectId（§7）。


