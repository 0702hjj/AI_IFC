# rooms.md —— rooms 设计规范（主 agent 逐 zone 加载）

> include：output_contract.md + work_area.md
>         + ../draw_api.md（dxfkit.draw 函数清单——建造段画图调用面）
>         + ../draw_composition.md（整层组装序——底座→墙→门窗→构件→标注→封存）

## 角色

本文件是 S2 房间设计规范（声明段 + 建造段）。主 agent 处理每个 zone 时加载本文件
（含上方 include 链，拼接后的全文进上下文），在该 zone 的承接分区内做两段式：
**声明段**（rooms.json）→ 断点② → **建造段**（draw 逐构件画 DXF）。
rooms 只做**分墙 + 房间标签**——门窗（openings）在 details 阶段统一规律生成。

## 输入清单（逐指针读取）

| 输入 | 怎么读 | 用途 |
|---|---|---|
| zone 包本层段（`derived/<zone>.json#floors[<rep>]`） | 读 geom 派生事实（edges/凹角/暗区/换算尺）+ outline | 设计依据（消费派生量） |
| 骨架段（`skeleton.json#zones[<zone>]` + 其 normalize 产物） | 读**分区几何**（core/corridor/大区/blocks 多边形）+ **分区标签** + **粗轴网**（派生） | 你的设计空间——分区已由骨架切好，你只在这分区内画分墙 |
| room_patterns 按需段 | 卡住时 `aidxfv3 gold query --params '{"kind":"pattern","pain":"<痛点>"}'` | 写法参照（pull 模式） |
| feedback（如有，`missions/<node>/feedback.md`） | 逐条读并响应 | 修正方向（断点② 修改时写入） |

## 声明写法（rooms DSL）

schema 见 `references/schemas/rooms.schema.json`（唯一契约，写前必读）。
**核心：房间由墙围出来。你声明墙，机器推房间。**

### ① 承接分区

```jsonc
"partitions": {
  "north_row": "seg:0",           // 本房间组的画布 = 骨架切割段 seg:0（大区被切割线切出的块）
  "south_row": "seg:1",           // 逐级分担：模型只在该段的边界里想怎么分房间
  "meeting_core": "corridor"      // 分区种类由 building_types + plan 引导已定
}
```
- 分区引用词表：`seg:<n>`（切割段）/ `corridor`（环廊带）/ `block:<id>`（骨架 blocks 认领段）/ `outline`（整层轮廓兜底）
- 分墙画在承接分区内——机器校验分区边界（R-01）
- 分区几何/标签在骨架 normalize 产物里——引用，用指针
- 画法路由：读分区标签决定怎么画（units 怎么切 / open_office 怎么分 / 核心筒怎么围）

### ② 墙声明（walls[]）

```jsonc
"walls": [
  {"key": "1F:int:0", "kind": "int", "t_mm": 120,
   "axis": [[12000, 8000], [12000, 14000]]},                              // straight 直墙（分墙）
  {"key": "1F:int:1", "kind": "int", "t_mm": 120,
   "path": [{"x": 2, "y": 0}, {"x": 2, "y": 2}, {"x": 3, "y": 2}]},      // axis-grid 正交分墙 run（索引粗轴网）
  {"key": "1F:ext:0", "kind": "ext", "t_mm": 200,
   "axis": [[0, 0], [0, 24000], [24000, 24000]]},                        // polyline 斜墙/折线（外墙贴轮廓）
  {"key": "1F:ext:1", "kind": "ext", "t_mm": 200,
   "arc": {"center": [12000, 12000], "r_mm": 6000, "a0_deg": 0, "a1_deg": 180}}  // arc 弧墙
]
```

| 形式 | 写法 | 何时用 |
|---|---|---|
| **straight** | `axis: [[x1,y1],[x2,y2]]`（绝对坐标，继承分区几何） | 单道分墙 |
| **polyline** | `axis: [[..],[..],[..]]`（多顶点折线） | 斜墙/折线（贴斜轮廓边） |
| **axis-grid** | `path: [{"x":i,"y":j},...]`（索引粗轴网） | 正交分墙 run（L/U 形），坐标机器算 |
| **arc** | `arc: {center, r_mm, a0_deg, a1_deg}` | 弧墙 |

- **key 稳定唯一**（建议 `<floor>:<kind>:<n>`，缺省机器自动分配）——details 阶段门窗挂墙定位靠它
- **墙必须落在承接分区内**（机器校验分区边界）
- **共边只声明一道墙**（相邻房间共享的墙 = 一道内墙）
- 房间由墙围出——墙画完贴标签（见 ③）

### ③ 房间标签（labels）

```jsonc
"labels": [
  {"room": "office_01", "type": "office", "area_sqm": 45, "frontage": "S",
   "at": [14000, 10000]},   // at 点落在墙围出的区域里 = 该区域叫 office_01
  {"room": "meeting_01", "type": "meeting", "area_sqm": 60,
   "at": [6000, 12000]},
  {"room": "corridor", "type": "corridor", "at": [9000, 15000]}
]
```
- `at` 点落在墙围出的闭合区域**内部**（机器校验：落区绑定房间）
- 房间名 + `type` 走类型包词表；`area_sqm` 是目标面积（R-03 校验：机器实测墙围区域 ∈ 目标 ±10%）
- `frontage`（可选，N/S/E/W…）：朝向声明——faces_south → frontage:"S"，R-05/R-08 机检用

### ④ 门窗（在 details 阶段）

**rooms 阶段不声明 openings**（schema 已拒绝该字段）。门窗在最后一步 details
由模型按统一规律批量处理（见 details.md），rooms 只管把墙画好、房间标好。

### 特殊构件（placemark 区域占位）

```jsonc
{"room": "stair_01", "type": "stair", "at": [4000, 6000],
 "placemark": {"kind": "stair"}}   // 标签 + 占位，位置走 labels 同机制
```

**设计期自查（R-01~R-09）**：

- **R-01**：墙画在承接分区内/轮廓内（贴边留 10mm 容差）
- **R-02**：共边只声明一道墙（两两围区不重叠）
- **R-03**：`area_sqm` ∈ program 区间；装不下走 `infeasible` 申报
- **R-04**：走廊 ≥ overrides.corridor_min_width_mm（或类型默认）
- **R-05**：`faces_south` → 南侧外墙贴分区/轮廓 S 边（satisfied_by 同句式）
- **R-07**：房间无几何邻居时预警（门图连通留给 details 阶段开门后对账）
- **R-08**：needs_exterior 房间外墙贴外边（Warning）
- **R-09**：deep_zone_ratio>0.3 时 deep 区应是贮藏/卫生间等非采光房间（Warning）

## 留痕义务

- `requirements_trace`：每条 requirement 写 `satisfied_by`（句式可机检，用方位词）
- `deviations` / `defaults_used`：记录使用情况
- **方位词用 `references/vocabulary/predicate_vocabulary.md`**（N/S/E/W/NE… + satisfied_by 同句式）

## geom 字段 → 设计用途

| geom 字段 | 设计用途 |
|---|---|
| `edges`（边方位/长度） | frontage 可行性——南房外墙贴 `edge:<id>` 有 dir=S 的边 |
| `exposure_m`（各方采光面长） | 南房面宽预算——Σ南房面宽 ≤ exposure_m.S，不够 → infeasible |
| `strip_area`（每米轴跨面积） | 容量估算——配比面积 ÷ strip_area = 大致开间 |
| `deep_zone`（暗区占比/区域） | 暗区放非采光房（贮藏/卫生间），触发 R-09 自查 |
| `core_anchor`（锚点语境） | 湿区贴位——靠 core 一侧画墙的依据 |
| `concave_corners`（凹角） | 异形分墙（polyline/arc）画法依据 |
| **分区标签**（normalize 产物） | **画法路由**——哪个分区按哪种画法切（units/open_office/core） |

**容量判断前先读这些字段**——消费派生事实。

## 知识查询（pull 模式）

卡住时（选形式拿不准/容量判断/satisfied_by 不会写）：
```
aidxfv3 gold query --project <golden.db> --params '{"kind":"pattern","pain":"P2-x","type":"<zone function>"}'
```

## 端到端示例

`references/examples/layered_push_example.json` + `README.md`——分区→画墙→机器产物
完整对照（东块两道分墙围出两房间 + 门沿墙定位的真实链路）。

## 容量判断

- 先排谁：采光房 → 湿区 → 标准开间 → 交通（按 R-08/R-03 优先级）
- 塞不下谁让：低优先级房间申报 `infeasible`

## 建造段

1. **复制** confirmed `skeleton.<floor>.dxf`（含分区轮廓底座）为 `floor.dxf`（一条 DXF 链）
2. 逐构件画房间：每道墙（walls 解析产物）= 一次 `wall_run` 构件调用（`aidxfv3 draw`
   或直接 import dxfkit.draw）；房间标签 = `tag` 构件
3. 画完 `saveas` 落盘（确定性封存）
   **检查由主 agent 完成后统一执行**：readback + reconcile 一次对账；
   对账 error 携报告修正，按报告（带 bbox 诊断）改
