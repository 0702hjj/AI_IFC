# W-0034: cad 语义 diff 引擎（XDATA key 对齐 + POST /diff + 历史版本物化）

- **状态：** done（关闭于「本迭代分支 feat/v0.6-cad-diff（PR 待提）」：Task 2 diff 引擎 c5a4833；Task 3 POST /diff + 物化 + 缓存/504 本提交——135 测试全绿）
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source，chunk B）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §1.2 语义 diff 段 + 「工作项建议」3
- **执行者/分支：** opencode / feat/v0.6-cad-diff

## 背景

chunk A（W-0032/W-0033）已交付 cad_script_lib（XDATA 确定性 key 身份）与 services/cad 骨架（staging/versions/run/save/rollback + 沙箱）。本项是 chunk B 第一块：实体级语义 diff 引擎。推广 `mcp/app/dxf_diff.py`——对齐键从 DXF handle 迁移到 XDATA key（handle 由 CAD 软件分配、重存全变，不能当身份用）。**与 IFC 的本质差异：CAD 里几何就是数据，坐标参与 diff**（IFC 侧 v1 明确不 diff 几何）。对应 IFC 侧 `diffing.py` + `ifc_materialize.py` + `routes_diff.py` 三件套。

## 涉及位置

- `services/cad/app/dxf_diffing.py`（新增，镜像 `services/ifc/app/diffing.py`）
- `services/cad/app/dxf_materialize.py`（新增，镜像 `services/ifc/app/ifc_materialize.py`：历史版本沙箱重建 + LRU）
- `services/cad/app/routes_diff.py`（新增，镜像 `services/ifc/app/routes_diff.py`）
- 参照：`mcp/app/dxf_diff.py`（handle 对齐旧实现，迁移其属性比较思路）、`services/ifc/tests/test_diff.py`（测试镜像源）

## 方案

1. **dxf_diffing.py**：对齐键 = XDATA key（APPID `AIDXF`）；无 key 实体降级策略（按类型+坐标指纹对齐或列入 unknown 明面化，不静默丢）。按实体类型比较属性集：LINE 端点、CIRCLE 圆心半径、LWPOLYLINE 顶点+bulge、TEXT/MTEXT 内容、INSERT 块名+变换、图层、线型、颜色。输出 `{added, removed, changed:[{key, changes:[{field,old,new}]}]}`，同 IFC diff schema。
2. **POST /models/{id}/diff**：实体级语义 diff 端点，行为镜像 IFC 侧——504 超时、不可变对（base==target 或两侧均为历史版本）结果缓存 `diff-{base}-{target}.json`、worker 持锁防并发重算。
3. **dxf_materialize.py**：历史版本 DXF 只留最新（chunk A 裁剪策略），diff 涉及历史版本时经沙箱重跑脚本重建，LRU 缓存物化结果。
4. **校验纪律**：业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；`test_verify_isolation` 契约测试继续绿。

**显式范围外：** locate/edit-call（W-0035）、Go 代理路由、render payload v2、MCP diff 切换。

## 验收标准

- `dxf_diffing.py`：XDATA key 对齐正确；无 key 实体有明确降级路径且不静默丢弃；输出 schema 与 IFC diff 一致。
- `POST /diff` 行为达标：504 超时、不可变对缓存命中、worker 持锁（并发同对只算一次）。
- `dxf_materialize.py`：历史版本经沙箱重建，LRU 生效；重建失败路径不污染缓存。
- 测试镜像 IFC 侧 `test_diff.py` 覆盖面（每类实体 added/removed/changed 字段级 golden 用例）。
- `cd services/cad && uv run --group dev pytest` 全绿。

## 测试要求

- diff golden：LINE/CIRCLE/LWPOLYLINE(含 bulge)/TEXT/MTEXT/INSERT 每类实体的 added/removed/changed 字段级用例（spec「测试要求」diff golden 条）。
- XDATA key 对齐：同脚本两跑 key 全同（确定性）；无 key 降级路径用例。
- 端点测试：504 超时、不可变对缓存（二次请求命中缓存文件）、worker 持锁并发去重。
- materialize 测试：历史版本沙箱重建、LRU 淘汰、失败不缓存。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
