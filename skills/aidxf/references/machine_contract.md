# machine_contract.md —— 机器命令契约

> 模型执行时的唯一命令契约：所有 CLI 命令的输入输出 schema、边界行为、退出码、
> 坐标归一化陷阱，都写在这里。执行按需取用，够用即止。
> 拿不准时：① 读本文件 ② `aidxfv3 gold query` 看金例 ③ 运行命令看真实产出。
> 画图调用面见 `draw_api.md` + `draw_composition.md`。

## 统一约定

- 输入输出都是 JSON；`--out <path>` 写文件，缺省写 stdout。
- 退出码：`0` 通过 / `1` FAIL（机检不过）/ `2` SchemaError（声明非法，结构化 `{error, at}` 回喂）。
- 所有几何坐标单位 `mm`，`origin=lot_southwest`，`north_deg=0`（y 增 = 北）。
- 时间戳不参与确定性（同一输入 → 同一输出，字节级）。

## 命令契约

### preprocess（S0）
```
aidxfv3 preprocess --plan plan.json --out derived/
```
- 输入：plan.json（只读）；输出 `derived/`：`floors.json`（DAG+归并）+ `<zone>.json` ×N（zone 包：geom 派生 + floors + vocab + gold_cards）+ `skeleton_base.json`（底座：outline/core anchor 机械注入）。
- zone 包 `<zone>.json` 关键段：`geom`（edges/凹角/暗区/core_anchor/strip_area/exposure）、`floors[<rep>]`（outline_mm/core/core_anchor_mm/program）。

### validate / normalize
```
aidxfv3 validate --dsl <skeleton|rooms>.json      # schema 门禁，exit 2 = SchemaError
aidxfv3 normalize --dsl <skeleton>.json           # skeleton DSL → 几何模型
aidxfv3 normalize --dsl <rooms>.json --params <skeleton>.json   # rooms DSL → 几何模型（自动过 normalize_skeleton）
```
- skeleton normalize 产出 `zones[0]`：`outline` / `cores[]`（polygon_mm）/ `corridor` / `cuts[]`（`{id, line_mm}`）/ `segments[]`（`{id, polygon_mm}`）/ `blocks[]`（认领段）/ `axis_grid_derived` / `partition_labels`。
- rooms normalize 产出：`rooms[]`（`{id, type, area_sqm, polygon_mm{vertices,centroid_mm}, boundary_walls[], neighbors[], frontage?, placemark?}`）+ `walls[]`（`{key, line_mm, length_m}`）。

### check
```
aidxfv3 check --plan plan.json                     # 轮廓级摄取 + 多 zone 对齐
aidxfv3 check --dsl skeleton.json --plan plan.json # 骨架级：越轮廓/blocks 语义/holes 对齐
aidxfv3 check --dsl rooms.json --geom skeleton.json  # 房间级 R-01~R-09（R-01 需 --plan 轮廓）
```
- 房间级规则：R-01 房间在轮廓内 / R-02 不重叠 / R-03 面积∈program±10% / R-05 朝向 / R-07 连通警告 / R-08 采光警告。
- **R-05**：朝向检查按「轮廓近原点」实现（`miny<100` 判 S）。轮廓偏移大时 frontage 声明会误报——在 requirements_trace 用 `satisfied_by` 记录朝向。

### preview / svg
```
aidxfv3 preview --dsl <skeleton|rooms>.json --out preview.svg   # 断点呈现（用后即弃）
aidxfv3 svg --dxf floor.dxf --out shot.svg                      # 视觉自检
```
- preview 出示意：轴网灰线 + core/房间色块，无工程语义。

### readback / reconcile
```
aidxfv3 readback --dxf floor.dxf --out readback.json   # DXF → 房间图（V2 词表 nodes/edges）
aidxfv3 reconcile --decl <rooms.geom> --graph <readback.json>
```
- **readback 坐标归一化**：输出全部平移原点（min=0），与声明绝对坐标（min=3000+）不同坐标系。对账前把回读坐标平移回声明系（用同名房间 centroid 差求偏移）。
- **reconcile 语义（单向防多）**：声明侧邻接 = normalize 几何共享边；回读侧邻接 = 只按画出的门推。V3 每房一扇门 → 门图是几何共墙的子集，只查回读超出声明（`read_adj - decl_adj` error），门超出共墙由 adjacency 统一抓。
- 检查项：room_missing（双向，id/质心匹配）/ area（<5%）/ adjacency（单向防多）。
- **`doorwin_issues`**（readback 输出字段）：门窗碰撞检测——`door_leaf_window`（门扇扫窗）/ `door_swing_window`（门 swing 弧扫窗）/ `door_door_leaf` / `door_door_swing`（相邻门扇重叠）。只报真相交（共线错开/端点接触/跨房间平行线不报）。非空即碰撞，details 阶段按避让规则修正。

### pack / state
```
aidxfv3 pack --node <zone>.<stage> --project <dir> [--type <building_type> --db golden.db]
aidxfv3 state sync       --project <dir>          # 对照 floors.json#dag.nodes 幂等补缺 mission
aidxfv3 state advance    --project <dir> --node <zone>.rooms   # 按产物推进单 mission 状态
aidxfv3 state reconcile  --project <dir>          # 中断恢复：扫 missions/ 汇总真实状态（不改写）
```
- **`<dir>`（工作区）= `{DATA}/skill-work/{projectID}`**（2026-08-21 起）：agent 注入的项目
  skill 工作区，主 agent 先 `get_skill_workdir` 拿绝对路径（或 `aidxfv3 init --project-id` 建），
  所有 aidxfv3 `--project`/`--project-id` 用它——projectId 隔离多项目不混淆；中间产物
  （derived/missions/deliver）落该工作区，禁止落其他位置。
- pack 在 `<dir>/missions/<node>/` 生成 `mission.json` + `prompt.md`（注入输入指针 + gold pattern DSL 片段）。
- `state` 负责状态记录；执行编排（线性逐 zone、断点、重做决策）由主 agent 亲自按 dispatch.md。
  状态推进规则（产物驱动）：rooms.json→declared；+geom.json→presented；
  +floor.dxf→built；+readback.json+geom_check.json(PASS)→done。
- 多 zone（异楼层裙房/塔楼）：`floors.json#dag.edges` 恒空，各 zone 独立 mission **顺序**推进——
  `state sync` 补出全部 mission，主 agent 逐个 zone 线性处理（前一个 done 再进下一个）。

> **`aidxfv3 deliver` 命令已退役（2026-08-21）**——它的两个职责都被 agent 工具链替代：
> 复制 DXF → S4-b script 工具链（init_model+stage/run/save）；building.json → S4-c agent 组装
> （deliver_building 工具）。CLI 不再提供 deliver 子命令。

### S4 交付改造（2026-08-21 起，deliver 不再「复制 DXF」）
- **S2/S3 画图时机器经 `dxfkit.record` 记录 draw 调用序列**（主 agent 画图前 `record.start()` +
  `record.wrap_draw_module(draw)`；draw_api 调用面不变，仅模块函数被包装为记录版）。
- **S4-a 固化**：`record.to_build_script(record.calls(), params={skeleton/rooms/details DSL})` 把
  调用序列固化为 archdxf 可运行的 **build() 脚本**（PARAMS 字面量 + build(params,out_path) 重放 +
  `__main__`，对齐 services/cad script-as-source 契约）——该 zone 的构建脚本事实源。
- **S4-b 注册平台模型**：主 agent 对每 zone 经 script 工具链注册——`init_model(dxf)`（分配 modelId）
  → `stage_script(build 脚本)` → `run_script`（沙箱跑 build 产 DXF）→ `save_script`（v1 版本化）。
  **这步替代了旧 deliver 的「复制 DXF 到 deliver/」**——DXF 交付 = 平台模型（modelId + script-as-source
  版本化 + viewer render.json 可看），不是游离文件。
- **S4-c building.json（agent 组装，非 CLI deliver）**：agent 组装（读 plan.json + 各 zone modelId）
  → `deliver_building` 工具落 PlanStore（plans/{projectID}/building.json 版本化）。zones[] 记
  **modelId**（平台模型指针，替代旧 DXF 文件路径 + sha256）+ 非几何属性（typology/note/area）。
  几何留在各 zone 平台模型的 DXF。**deliver.py 不知道 agent init_model 的 modelId——building.json
  只能 agent 组装**。
- **deliver 后清理中间产物**：S4 完成后清空工作区过程产物（missions/derived/floor.dxf 过程态）——
  事实源已转移到平台模型 build() 脚本（models/{modelId}/scripts/），再次修改走平台模型
  script-as-source（改 build 脚本 → 沙箱跑），不依赖过程残留（避免误导）。building.json 与
  build() 脚本随平台模型/方案产物保留。

### gold
```
aidxfv3 gold query --project <golden.db> --params '{"kind":"case|pattern","type":"<residence|office|...>","pain":"P2-x"}'
aidxfv3 gold replay --project <case_dir>     # G2：可重放（exit 0 = PASS）
```
- query 返回命中卡片（DSL 片段可改参数套用）；replay 产 `replay_check.json`。

## 坐标/归一化陷阱速查

| 现象 | 原因 | 处置 |
|---|---|---|
| readback 坐标全变小（min=0） | readback 统一平移原点 | 对账前用同名房间 centroid 求偏移平移回去 |
| skeleton 切割线 ~1.4mm 斜 | 锚点 `at` 比例浮点 | `at` 用足精度（如 0.824074 而非 0.8241） |
| rooms 墙合围不上（重叠） | 分区画布边界与墙未节点化 | 用 `outline` 单画布 + 显式全墙 |
| frontage=S 误报 R-05 | 朝向检查按原点附近实现 | 朝南用 requirements_trace.satisfied_by 记录 |

## 画图调用面

逐构件画法见 `draw_api.md`（函数签名齐全，含 `draw_partition_base`/`wall_run`/`door`/`window`/`draw_column`/`room_label` 等）。
画图按 draw_api.md + draw_composition.md 执行。
