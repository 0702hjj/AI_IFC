# services/cad Chunk B（语义 diff + locate/edit-call）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** spec `2026-08-12-services-cad-script-as-source-design.md` 工作项 3-4：XDATA key 对齐的实体级语义 diff（含历史版本物化与 diff 缓存）+ locate/edit-call（key→callsite 定位与 libcst 标量改写）。

**Architecture:** 镜像 services/ifc 的 diff/locate/edit 三件套：diffing.py（扁平 schema）→ dxf_diffing.py（XDATA key 对齐，几何参与 diff——CAD 与 IFC 的本质差异）；routes_diff.py（线程池 + 504 超时 + worker 内持锁 + 不可变对缓存）；script_edit.py（libcst 无损标量改写）+ locate/edit-call 端点（map 信封 scriptHash stale 语义）。

**Tech Stack:** Python 3.10 + FastAPI + ezdxf + libcst（本 chunk 新增依赖）；pytest。

## Global Constraints

- 分支 `feat/v0.6-cad-diff`（已建，自 main ee0279a）；commit 中文前缀式；一天最多 1 PR。
- TDD：先失败测试后实现；测试量 ≥ 实现量。
- 校验隔离：`raise HTTPException` 只准在 verify*/validate* 或 route_common.py；ALLOWLIST 保持空。
- 自包含：不引用仓外路径；libcst 走 uv 依赖（`libcst>=1.5`，与 services/ifc 同线）。
- **执行门禁（用户 2026-08-13 指示）**：Task 4（locate/edit-call，CAD 编辑）开工前必须先向用户确认。
- 遗留携带项（终审裁决）：Task 2 顺手删 `NAMESPACE_AIDXF` 死常量（diff 不用 uuid5）；Task 3 给 `route_common._locks` 加 LRU 逐出（上限 1024，超了丢最旧——与 StagingRegistry max_staging 风格一致）；Task 4 移植 ifc `_load_map_envelope`/`_map_is_stale` 判定逻辑保持两侧同形。
- 分期决策：MCP `dxf_upload_modified` 切新 diff 引擎属 spec 工作项 7（chunk C），本 chunk 不动 mcp/。Go 代理同属 chunk C。

---

### Task 1: 立项 W-0034/W-0035 + PLAN v0.6 扩行

**Files:**
- Create: `docs/work/items/W-0034-cad-semantic-diff.md`
- Create: `docs/work/items/W-0035-cad-locate-edit-call.md`
- Modify: `docs/work/PLAN-v0.1.0.md`（v0.6 行扩为 chunk A ✅ + chunk B 行）

- [ ] **Step 1: item 文件**（模板 docs/work/README.md，风格照 W-0033）

- W-0034「cad 语义 diff 引擎」：P1，Milestone v0.6，来源 spec §1.2 语义 diff 段。验收：dxf_diffing.py（XDATA key 对齐 + 无 key 降级）+ POST /diff（504 超时/不可变对缓存/worker 持锁）+ dxf_materialize（历史版本沙箱重建 LRU）+ 测试镜像 ifc test_diff 覆盖。
- W-0035「cad locate/edit-call」：P1，来源 spec §1.2 端点表 + §三展望的 locate 部分。验收：GET /script/locate?key=（stale 降级 {found:false,stale:true}）+ POST /script/edit-call（409 stale fail-closed、traced 422、零副作用失败路径）+ libcst rewrite 单测 + 端点测试镜像 ifc 覆盖。**注明：开工需用户确认（CAD 编辑门禁）。**

- [ ] **Step 2: PLAN v0.6 行改两行**（chunk A 行已 ✅ 保持；加 chunk B 行：W-0034/W-0035，完成判据=diff 引擎与 locate/edit-call 测试绿）
- [ ] **Step 3: Commit** `docs(work): W-0034/W-0035 立项 + PLAN v0.6 chunk B 行`

---

### Task 2: dxf_diffing.py 语义 diff 引擎（TDD，纯函数）

**Files:**
- Create: `services/cad/app/dxf_diffing.py`
- Test: `services/cad/tests/test_dxf_diffing.py`
- Modify: `skills/aidxfv/v1/scripts/flows/cad_script_lib.py`（删 NAMESPACE_AIDXF 死常量，终审携带项）
- Test: `tests/skill/test_cad_script_lib.py`（如有断言该常量则同步删）

**Interfaces（Produces——Task 3/4 与 chunk C web 依赖）:**

```python
# dxf_diffing.py
def compute_diff(base_path: str, target_path: str) -> dict
# 返回 {"added": [key], "removed": [key], "changed": [{"key": key, "changes": [{"field","old","new"}]}]}
# added/removed 为排序后的 key 列表（str）；无 key 实体永不进 changed
```

- [ ] **Step 1: 写失败测试**

fixture：用 cad_script_lib 工厂造 base.dxf / target.dxf（reset_state + add_entity + write_and_validate，ezdxf.readfile 可读）。覆盖：

```python
class TestAlignment:   # 对齐键语义
    - test_added_removed_by_xdata_key          # 加/删实体 → added/removed 含正确 key
    - test_handle_change_still_aligned         # 同 key 不同 handle（重存后）不产生增删（XDATA 对齐的核心价值，mcp 版踩坑点）
    - test_keyless_entities_counted_only       # 无 XDATA 实体：两侧签名完全一致→不报；只一侧有→added/removed 带 "nokey:" 前缀条目；永不进 changed
class TestFieldDiff:   # 每类实体 golden（镜像 spec §1.2 属性集）
    - test_line_endpoint_change                # LINE start/end
    - test_circle_radius_change                # CIRCLE center/radius
    - test_arc_angles_change                   # ARC center/radius/start_angle/end_angle
    - test_lwpolyline_points_and_bulge_change  # 顶点 + bulge（mcp 版漏 bulge，此处必须覆盖）
    - test_text_and_mtext_content_change       # text/insert
    - test_insert_block_transform_change       # INSERT name/insert
    - test_layer_color_linetype_change         # 实体级 layer/color/linetype 属性
    - test_coordinate_change_is_a_diff         # CAD 本质差异：几何坐标参与 diff（IFC 侧 v1 不做）
class TestShape:
    - test_output_schema_sorted_deterministic  # added/removed 排序、两跑结果全等
    - test_jsonable_values                     # tuple/Vec3 → 标量 list，round 6 位
    - test_empty_diff                          # 同文件 → 三空
```

- [ ] **Step 2: 跑确认失败** → `cd services/cad && uv run --group dev pytest tests/test_dxf_diffing.py` → 模块不存在

- [ ] **Step 3: 实现 dxf_diffing.py**

推广 `mcp/app/dxf_diff.py`（:29-138）到 XDATA key 对齐：

```python
_PRECISION = 6
def _entity_key(entity) -> str | None      # 委托 cad_script_lib.get_entity_key（经 flows_dir sys.path，同 script_runner 的 _load_cad_script_lib 模式；单点 loader 放 dxf_diffing 顶部）
def _signature(entity) -> tuple | None     # 按 dxftype 的属性集：LINE(start,end) / LWPOLYLINE(points 含 bulge) / CIRCLE(center,radius) / ARC(center,radius,start_angle,end_angle) / TEXT(text,insert) / MTEXT(text,insert) / INSERT(name,insert)；外加公共三字段 layer/color/linetype；未知类型 → None
def _entities_by_key(doc) -> dict          # modelspace 遍历：有 key → key 对齐；无 key → ("nokey", type, signature) 合成键仅用于增删判定
def compute_diff(base_path, target_path) -> dict
```

- 同 key 不同 dxftype → changes=[{"field":"type",...}]（mcp :101-104 语义）。
- 无 key 实体：签名在两侧同时出现且唯一 → 视为未变（不报）；否则进 added/removed，entry key 用 `nokey:{type}:{i}`（i 为稳定枚举序——按 (type, signature) 排序后编号，保证确定性）。**无 key 实体永不进 changed**。
- `_jsonable`：Vec3/tuple → [x,y,z] round 6；其余 str()。
- 文件头注释写明与 mcp/app/dxf_diff.py 的演进关系（handle→XDATA key 迁移，bulge 补齐）。

- [ ] **Step 4: 删 NAMESPACE_AIDXF + 全量绿**

`cd services/cad && uv run --group dev pytest`（含既有 95）+ `.ci-venv/bin/python -m pytest tests/skill/ -q`。

- [ ] **Step 5: Commit** `feat(services/cad): 语义 diff 引擎——XDATA key 对齐 + 无 key 降级 + 全实体属性集（W-0034 上半）`

---

### Task 3: routes_diff + dxf_materialize + diff 缓存（TDD）

**Files:**
- Create: `services/cad/app/routes_diff.py`、`dxf_materialize.py`
- Modify: `services/cad/app/main.py`（挂 routes_diff）、`config.py`（补 `diff_timeout_s`，env `CAD_SERVICE_DIFF_TIMEOUT_S` 默认 60）、`route_common.py`（_locks 加 LRU 逐出上限 1024）
- Test: `services/cad/tests/test_diff.py`、`test_dxf_lazy_materialize.py`

**Interfaces:**
- Consumes: Task 2 `dxf_diffing.compute_diff`
- Produces: `POST /models/{id}/diff` body `{base: str, target: str}`（target 接受 `"current"`）→ `{base, target, added, removed, changed}`；不可变对缓存 `versions/diff-{base}-{target}.json`（target=="current" 不缓存）；`GET /versions` 已在 chunk A（routes_scripts），本任务不动

- [ ] **Step 1: 写失败测试**（镜像 services/ifc/tests/test_diff.py + test_ifc_lazy_materialize.py 语义，适配 DXF）

- test_diff.py 用例面：版本对 diff（经两次 save 造 v1/v2）、target=current 不缓存、结果缓存（第二次请求命中 diff-*.json——可用 mtime/内容断言或 spy）、未知版本 404、无 commit 404、缺参数 422、坏 model id 422、未知模型 404、超时 504（monkeypatch compute 睡过 diff_timeout_s）、超时后残余 worker 串行化下一 diff（AGENTS 纪律 5：条件等待非 sleep）。
- test_dxf_lazy_materialize.py：只物化最新（prune 后旧版本 .dxf 不在盘）、diff 请求旧版本时按需沙箱重建进 `dxf_cache/`（LRU 4）、重建产物可被 diff 消费。

- [ ] **Step 2: 实现**

- `dxf_materialize.py` 镜像 `services/ifc/app/ifc_materialize.py`：经 script_runner 沙箱重跑 `scripts/v{n}.py` → `dxf_cache/v{n}.dxf`（LRU 上限 4，逐出 os.remove；env 或常量照 ifc 侧）。
- `routes_diff.py` 镜像 `services/ifc/app/routes_diff.py`：`_DIFF_EXECUTOR`（max_workers=2）+ `_run_diff_with_timeout`（504）；`_compute_payload` 在 worker 内持 `model_lock`（acquire/release 同线程，7db0f4a 语义）；`_version_or_404` 先 materialize 再 404；缓存读 :110-117 / 写 :139-143 模式（tmp+os.replace）。
- verify 纪律：body 校验进 pydantic 声明式；404/504 的 raise 位置进 verify*/route_common——404 翻译参考 ifc 侧 `verify_*` 命名（如 `verify_version_ref`）；若 ifc 侧对应逻辑在 ALLOWLIST，cad 侧不允许新增白名单项，改写为 verify 函数形态。
- `route_common._locks` 加逐出：`len(_locks) > 1024` 时丢最旧（OrderedDict move_to_end on access + popitem(last=False)）。

- [ ] **Step 3: 全量绿 + W-0034 置 done + Commit** `feat(services/cad): POST /diff + 历史版本物化 + diff 缓存/504（W-0034 下半）`

---

### Task 4: locate + edit-call（⚠️ 开工前必须先取得用户确认——CAD 编辑门禁）

**Files:**
- Create: `services/cad/app/script_edit.py`
- Modify: `services/cad/app/routes_scripts.py`（加 locate/edit-call 端点 + `_current_map_path`/`_read_current_map`/`_map_is_stale` helper 移植）、`services/cad/pyproject.toml`（加 `libcst>=1.5`）+ `uv lock`
- Test: `services/cad/tests/test_script_edit.py`、`test_script_locate.py`

**Interfaces:**
- Consumes: chunk A map 信封（`current.map.json` scriptHash）、cad_script_lib callsite entry `{line,col,snippet,origin,params_keys}`
- Produces: `GET /models/{id}/script/locate?key=` → `{found, key, line?, col?, snippet?, origin?, params_keys?, stale?}`；`POST /models/{id}/script/edit-call` body `{key, argument, value}` → 200 `{modelId, staged, script}`；两端点仅服务直连（不经 Go 代理——chunk C 落实代理边界）

- [ ] **Step 1: 写失败测试**

- test_script_edit.py 镜像 ifc 26 用例语义（rewrite 单元 12 + 端点 14）：bool 非 int、追加缺失实参、只动目标行、注释空行保留、无 Call/语法错/非标量/非标识符/非有限 float 各错误分支；端点：stages_and_reruns、params origin 改其他实参、未知 key 404、无 map 404、traced 422、各 422、build 失败零副作用、未跑暂存 409 零副作用、undo 后 409、legacy 裸 map 409、happy path hash 一致。
- test_script_locate.py 镜像 15 用例语义，适配 DXF：key 直接定位（无 guid→designKey 转换——locate 参数就是 XDATA key）；无 key 实体/未知 key → found:false；stale 降级 200；undo/staged 未跑/legacy 裸 map 各 stale 分支；rerun 清 stale。

- [ ] **Step 2: 实现**

- `script_edit.py`：镜像 services/ifc/app/script_edit.py（libcst `rewrite_call_argument(script, line, argument, value)`，PositionProvider 定位，bool 先于 int，str 走 json.dumps ensure_ascii=False）——逐行可搬，无 ifc 依赖。
- routes_scripts.py 加端点（镜像 ifc :514-588 流程）：
  - locate：读 current.map.json 信封 → entries.get(key)；stale → 200 `{found:false, key, stale:true}` 降级（绝不让前端跳错误行）；命中 → `{found:true, key, **entry}`。注意 cad 侧无 registry/by_guid——key 即入参，省掉 IFC 前两步。
  - edit-call：`_current_or_409` → map 缺失 404 → stale 409 fail-closed → key 不在 map 404 → origin==traced 422 → `rewrite_call_argument`（ValueError→422）→ `_run_into_uploads`（沙箱 run + 发 map）→ `staging.push` → 200。任何失败零副作用。
  - helper 移植保持 ifc 同形：`_read_current_map`（缺文件/坏 JSON → (None,None)；缺 scriptHash/map 的旧裸 map → (None,{}) 按 stale 处理）、`_map_is_stale`（与 staging tip 的 script_hash 比较）。

- [ ] **Step 3: 全量绿 + 1:1 对账 + W-0035 置 done + Commit** `feat(services/cad): locate/edit-call——key 定位 + libcst 标量改写 + stale fail-closed（W-0035）`

---

### Task 5: 收口

**Files:**
- Modify: `services/cad/README.md`（端点表补 /diff、locate、edit-call；测试计数同步）
- Modify: `AGENTS.md`（services/cad 行测试计数；逻辑二状态行改「diff/locate/edit-call 已交付，Go 代理/render/前端待续」）
- Modify: `docs/work/PLAN-v0.1.0.md`（chunk B 行 ✅）
- Modify: `docs/work/items/W-0030-services-cad-direction.md`（加注 chunk B 落地）

- [ ] **Step 1: 改 + 复跑 `uv run --group dev pytest`（services/cad）**
- [ ] **Step 2: Commit** `docs: services/cad chunk B 收口——README/AGENTS/PLAN 同步`

---

## Self-Review 记录

- Spec 覆盖：工作项 3→Task 2/3；工作项 4→Task 4；测试要求 diff golden→Task 2 用例表；工作项 5-7 明示 chunk C。
- 占位符：镜像类实现给了源 file:line 锚点（routes_diff.py:110-117 等）；新语义（无 key 降级、nokey 合成键）给了完整规则。
- 类型一致：`compute_diff` 返回形状在 Task 2 定义/测试、Task 3 消费；locate 入参 `key`（非 guid）在 Task 4 两端点一致。
- 风险：无 key 降级策略是新设计（spec 未细化）——已定为「签名双侧唯一→未变，否则只计增删」，测试锁定；materialize 依赖沙箱重跑确定性（cad_script_lib reset_state 语义已在 chunk A 锁定）。
