# dsl_walkthrough.md —— W0 T06 DSL 可行性走查记录

> 2026-08-10。schema 冻结前的最后一道纸面验证：**DSL 若表达不了真实建筑，
> W1-W4 全部白建**。素材：R-01 真实 DXF + 三个合成极端轮廓。
> 走查方式：按 geo_cognition §5/§6 手写 skeleton.json / rooms.json 全文，
> 不借助任何工具，纯验证表达力。缺口 → 裁决 → 回 T02/T03 修订 schema → 冻结。

---

## 1. 素材清单

### 素材 A：R-01 真实住宅（AI_CAD/data/floorplan_结构.dxf）

AIA 标准图层独立住宅。经 ezdxf 提取（A-FOOTPRINT 层）：

- **主轮廓**（L 形带台阶凹口，无弧，14 去重点，mm）：
  `(1200,1000) (1200,8823) (-4947,8823) (-6268,8823) (-16479,8823) (-16479,-321)`
  `(-12262,-321) (-12262,-930) (-8452,-930) (-8452,-321) (-7741,-321) (-7741,1000) (-5557,1000) (-3785,1000)`
  - 总尺寸：17679mm (E-W) × 9753mm (N-S)
  - 南侧两级台阶凹口（-12262~-8452 深 609mm；-7741~-5557 内缩至 y=1000）
- **附属 footprint 块 ×3**：车库（POLY[3] 6.76×6.5m）、门廊（POLY[4] 2.5×4.4m）、小体块（POLY[2] 3.6×1.3m）
- 功能假设（住宅类型包）：living 25㎡ / kitchen 10㎡ / bedroom×3 各 12㎡ / bathroom×2 各 5㎡ / garage 24㎡

### 素材 B：极端轮廓①带真弧边（合成）

20m×12m 矩形，东端两角为 R=3000mm 圆弧。
ring: `vertices [[0,0],[20000,0],[20000,12000],[0,12000]]` +
`arcs [{at:1, center:[17000,9000], radius:3000}, {at:2, center:[17000,3000], radius:3000}]`

### 素材 C：极端轮廓②带中庭孔（合成）

24m×18m 外框，中央 8m×6m 中庭孔。
`outer [[0,0],[24000,0],[24000,18000],[0,18000]]` + `holes [[[8000,6000],[16000,6000],[16000,12000],[8000,12000]]]`

### 素材 D：极端轮廓③深板进深 >16m（合成）

24m×20m 矩形无孔，`deep_zone_ratio` 触发暗区（距边 >8m 的中央区）。

---

## 2. 走查 A：R-01 真实住宅

### 2.1 skeleton.json 全文（纸面）

```jsonc
{
  "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
  "zones": [{
    "zone": "house",
    "axis_grid": {
      // 锚 dominant_axes（轮廓主边）：x∈[-16479,1200] 分 5 跨，y∈[-930,8823] 分 3 跨
      "x": [-16479, -13000, -9500, -6000, -2500, 1200],
      "y": [-930, 2500, 5800, 8823]
    },
    "core": null,                              // ★无核心筒（单层住宅）——见缺口 G-01
    "corridor": {                              // 过道：北段卧室群之间的交通
      "form": "path",
      "path": [{"x": 1, "y": 2}, {"x": 4, "y": 2}],   // 轴网路径，y 轴第 2 跨
      "width_mm": 1200
    },
    "main_partitions": [
      {"path": [{"x": 0, "y": 1}, {"x": 5, "y": 1}], "role": "起居/私区 分界"}
    ],
    "special_openings": [],
    "typology": "单层住宅 L 形",
    "typology_reason": "edges 含南侧两级台阶凹口，concave_corners 在 SE，无孔",
    "note_responses": [],
    "deviations": [], "defaults_used": []
  }]
}
```

### 2.2 rooms.json 全文（纸面）

```jsonc
{
  "floor": "house_1f",
  "axis_grid_ref": "skeleton.json#zones[house].axis_grid",
  "rooms": [
    {"id": "living_01", "type": "living", "area_sqm": 25,
     "loc": {"on_edge": "S", "after": "garage_01", "w_m": 5.0},   // 南向采光
     "frontage": "S"},
    {"id": "kitchen_01", "type": "kitchen", "area_sqm": 10,
     "loc": {"between_axes": {"x": [0, 2], "y": [0, 1]}}},        // 西端
    {"id": "bedroom_01", "type": "bedroom", "area_sqm": 12,
     "loc": {"between_axes": {"x": [1, 2], "y": [2, 3]}}},        // 北向
    {"id": "bedroom_02", "type": "bedroom", "area_sqm": 12,
     "loc": {"between_axes": {"x": [2, 3], "y": [2, 3]}}},
    {"id": "bedroom_03", "type": "bedroom", "area_sqm": 12,
     "loc": {"between_axes": {"x": [3, 4], "y": [2, 3]}}},
    {"id": "bathroom_01", "type": "bathroom", "area_sqm": 5,
     "loc": {"adjacent_to": "kitchen_01", "side": "N"}},          // ★无 core，改邻厨房——见缺口 G-04
    {"id": "bathroom_02", "type": "bathroom", "area_sqm": 5,
     "loc": {"between_axes": {"x": [4, 5], "y": [1, 2]}}},
    {"id": "garage_01", "type": "garage", "area_sqm": 24,
     "loc": {"between_axes": {"x": [3, 5], "y": [0, 1]}}}         // 附属块
  ],
  "openings": [
    {"room": "living_01", "on": "corridor", "along_m": 1.0, "w_mm": 900, "type": "door"},
    {"room": "bedroom_01", "on": "edge:N", "along_m": 1.8, "w_mm": 1500, "type": "window"},
    {"room": "bedroom_02", "on": "edge:N", "along_m": 1.8, "w_mm": 1500, "type": "window"},
    {"room": "bedroom_03", "on": "edge:N", "along_m": 1.8, "w_mm": 1500, "type": "window"}
  ],
  "requirements_trace": [
    {"requirement": "bedroom faces_south (must)",
     "satisfied_by": "bedroom_01..03 位于北带，frontage 缺省——未满足，改南带（见走查记录）"}
  ],
  "deviations": [], "defaults_used": []
}
```

### 2.3 走查记录（R-01）

| 检查点 | 结果 | 说明 |
|---|---|---|
| 四 loc 形式能否覆盖全部房间 | **大体能，1 次想发明第五种** | bathroom 无 core 可邻 → 想造 "adjacent_to any-room"；实为 G-04 放宽即可 |
| 轴网锚住真实墙体？ | **部分** | 真实墙厚 200 不贴轴线；on_edge 的 w_m 兜底够用（房间按轴带排布，墙由 normalizer 沿共享边生成） |
| 墙不贴轴房间怎么写 | on_edge w_m 兜底 | 记录：需要 normalizer 把 on_edge 房间沿边带布置、w_m 深度 + after 沿边排序 |
| requirements_trace 可机检吗 | **可**（但本走查暴露用户意图矛盾） | "bedroom faces_south" 与北带卧室冲突 → 应回 S1 调整骨架，或接受 R-05 FAIL 回喂。**发现：requirements 冲突应在 S1 由主 agent 裁决，不是 rooms 硬扛** |
| 弧边/孔洞引用 | 本素材无弧无孔 | 见素材 B/C |
| 附属 footprint 块 | 可表达（garage 用 between_axes 落在附属块内） | 注意：garage 落在 outline_mm[1]（独立块）内，normalizer 需按"各块独立房间归属"检查 R-01 |

---

## 3. 走查 B：极端轮廓①带真弧边

### 3.1 skeleton 声明

```jsonc
{
  "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
  "zones": [{
    "zone": "arc_hall",
    "axis_grid": {"x": [0, 4000, 8000, 12000, 16000, 20000], "y": [0, 3000, 6000, 9000, 12000]},
    "core": null,
    "corridor": {"form": "path", "path": [{"x": 0, "y": 1}, {"x": 5, "y": 1}], "width_mm": 2400},
    "main_partitions": [],
    "special_openings": [],
    "typology": "弧角大厅",
    "typology_reason": "edges 含 2 条 arc（东端 R3000），角部弧形房间沿弧边布置",
    "note_responses": [], "deviations": [], "defaults_used": []
  }]
}
```

### 3.2 rooms 声明（关键：贴弧边房间）

```jsonc
{
  "floor": "arc_hall_1f",
  "axis_grid_ref": "skeleton.json#zones[arc_hall].axis_grid",
  "rooms": [
    {"id": "lobby_01", "type": "lobby", "area_sqm": 60,
     "loc": {"on_edge": "edge:0", "after": null, "w_m": 6.0},   // ★贴弧边：引用 edges[0]（弧段）——见缺口 G-03
     "frontage": "E"},
    {"id": "showroom_01", "type": "showroom", "area_sqm": 80,
     "loc": {"between_axes": {"x": [0, 4], "y": [1, 3]}}}
  ],
  "openings": [
    {"room": "lobby_01", "on": "edge:0", "along_m": 2.0, "w_mm": 1800, "type": "door"}
  ],
  "requirements_trace": [], "deviations": [], "defaults_used": []
}
```

### 3.3 走查记录（弧边）

| 检查点 | 结果 | 说明 |
|---|---|---|
| 弧边 on_edge:"edge:<id>" 引用够吗 | **基本够** | 需要 schema 允许 on_edge 为方位词或 "edge:<id>" 引用（G-03） |
| 贴弧边房间的"深度"语义 | **有缺口** | w_m 是直线深度，弧面房间内侧不是等宽矩形——标**限制**：弧面房间按弦宽近似 + 特殊形态豁免（R 规则"只检查功能不检查形态"） |
| 弧段在轴网上无法索引 | 绕过：用 on_edge 而非 between_axes | 弧段边不挂轴网，是 edges 清单的事实（geo_cognition §0 已设计） |
| 弧角 open（door） | on:"edge:0" + along_m 可表达 | 位置沿弧度量，normalizer 需支持弧段沿弧定位（W1 实现细节） |

---

## 4. 走查 C：极端轮廓②带中庭孔

### 4.1 skeleton 声明

```jsonc
{
  "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
  "zones": [{
    "zone": "atrium_floor",
    "axis_grid": {"x": [0, 4000, 8000, 12000, 16000, 20000, 24000],
                  "y": [0, 3000, 6000, 9000, 12000, 15000, 18000]},
    "core": null,
    "corridor": {"form": "ring", "around": "holes[0]", "width_mm": 1800},   // ★geo_cognition §5 示例形态，直接命中
    "main_partitions": [
      {"path": [{"x": 0, "y": 0}, {"x": 0, "y": 6}], "role": "东区 与 中庭环廊 分界"}
    ],
    "special_openings": [{"at_axes": {"x": [2, 4], "y": [2, 4]}, "reason": "note: 中庭上空"}],
    "typology": "中庭环绕",
    "typology_reason": "holes[0] 居中 48㎡，deep_zone_ratio 低 → 环绕式（geo_cognition Q1 引用 holes）",
    "note_responses": [], "deviations": [], "defaults_used": []
  }]
}
```

### 4.2 rooms 声明（环孔排布）

```jsonc
{
  "floor": "atrium_1f",
  "axis_grid_ref": "skeleton.json#zones[atrium_floor].axis_grid",
  "rooms": [
    {"id": "shop_01", "type": "shop", "area_sqm": 45,
     "loc": {"on_edge": "S", "after": null, "w_m": 6.0}},          // 外圈南
    {"id": "shop_02", "type": "shop", "area_sqm": 40,
     "loc": {"on_edge": "hole:0", "after": null, "w_m": 4.5}},    // ★内圈贴孔——见缺口 G-03
     "frontage": "hole:0"},
    {"id": "corridor_ring", "type": "corridor",
     "loc": {"follows": "skeleton.corridor"}}                      // 继承骨架走廊
  ],
  "openings": [
    {"room": "shop_01", "on": "corridor_ring", "along_m": 1.5, "w_mm": 1200, "type": "door"}
  ],
  "requirements_trace": [], "deviations": [], "defaults_used": []
}
```

### 4.3 走查记录（中庭孔）

| 检查点 | 结果 | 说明 |
|---|---|---|
| 中庭孔骨架 | **命中设计形态** | corridor ring around:"holes[0]" 与 §5 示例完全一致，表达力强 |
| 内圈房间贴孔 | on_edge:"hole:0" 可表达（G-03） | 孔边房间 frontage 也可引用 "hole:0"——R-08 采光面检查需认孔边为"可采光边"？**裁决：孔边不算 exterior，frontage:"hole:0" 用于孔边贴邻，R-08 只查外轮廓边** |
| special_openings 表达中庭 | 用 at_axes 标注孔位 | 但孔其实已在 holes 里，special_openings 语义更偏"吊装孔/设备孔"——文档需澄清二者分工（W1 细节） |

---

## 5. 走查 D：极端轮廓③深板进深 >16m

### 5.1 skeleton 声明

```jsonc
{
  "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
  "zones": [{
    "zone": "deep_plate",
    "axis_grid": {"x": [0, 4000, 8000, 12000, 16000, 20000, 24000],
                  "y": [0, 4000, 8000, 12000, 16000, 20000]},
    "core": {"anchor": [12000, 10000], "extent": {"x": [2, 4], "y": [2, 3]}},   // ★深板中央核心筒——core 在此有实际意义
    "corridor": {"form": "path", "path": [{"x": 0, "y": 1}, {"x": 6, "y": 1}], "width_mm": 2400},
    "main_partitions": [],
    "special_openings": [],
    "typology": "中央核心深板",
    "typology_reason": "depth.max_m 20 > 16，deep_zone_region 中央 → 核心筒占暗区",
    "note_responses": [], "deviations": [], "defaults_used": []
  }]
}
```

### 5.2 rooms 声明

```jsonc
{
  "floor": "deep_1f",
  "axis_grid_ref": "skeleton.json#zones[deep_plate].axis_grid",
  "rooms": [
    {"id": "core_01", "type": "core", "area_sqm": 30,
     "loc": {"adjacent_to": "core", "side": "all"}},
    {"id": "office_01", "type": "office", "area_sqm": 40,
     "loc": {"on_edge": "N", "after": null, "w_m": 8.0}, "frontage": "N"},   // 南侧深区办公室无外窗——R-09 预警
    {"id": "storage_01", "type": "storage", "area_sqm": 20,
     "loc": {"between_axes": {"x": [1, 2], "y": [2, 3]}}}                   // ★暗区放贮藏——R-09 通过
  ],
  "openings": [],
  "requirements_trace": [],
  "deviations": [], "defaults_used": []
}
```

### 5.3 走查记录（深板）

| 检查点 | 结果 | 说明 |
|---|---|---|
| 深板暗区核心筒 | **可表达** | core 在此是必须的（中央核心），与 R-01 住宅形成对比 → **core 必填/可选应由类型包决定，schema 层允许 null（G-01）** |
| 暗区房间类型 | storage/bathroom 等非采光房可用 between_axes 放中央 | R-09 Warning 检查 deep 区类型 |
| 进深 >16m 触发的换算 | strip_area 心算可走 | per_m_x_sqm = 进深 20m → 每米轴跨 20㎡；30㎡ 核心 ≈ 1.5 跨，心算 OK |

---

## 6. DSL 缺口清单 → 裁决

| # | 缺口 | 出现场景 | 裁决 | 落地 |
|---|---|---|---|---|
| **G-01** | `core` 对无核心筒建筑（单层住宅/厂房/门厅）是"无" | 素材 A（住宅）、B（弧厅） | **core 改为可选**：`oneOf [{anchor,extent}, null]`，存在时 T4 锁锚、R-06 校验；不存在时 adjacent_to:"core" 禁用（SchemaError） | T02 schema 修订 |
| **G-02** | `corridor` 对无走廊小建筑（单层住宅穿套）可能无独立走廊 | 素材 A（住宅过道其实有，但更小的套间没有） | **corridor 改为可选**；缺省时房间靠 R-07 门图连通（门对门/穿套） | T02 schema 修订 |
| **G-03** | `on_edge` 只能写方位词，不能引用弧边/孔边（`edge:<id>` / `hole:<i>`） | 素材 B（弧边）、C（孔边） | **on_edge 支持 oneOf：方位词 \| `edge:<id>` \| `hole:<i>`**；frontage 同。R-08 只查外轮廓边，孔边 frontage 不触发采光 | T02/T03 schema 修订 |
| **G-04** | `adjacent_to` 引用目标只有 core/corridor，房间想邻接任意已确认房间（bathroom 邻 kitchen） | 素材 A（bathroom） | **adjacent_to 目标放宽为：骨架目标（core/corridor）\| 同级房间 id**（引用目标必须是骨架确认产物或同级房间——DSL 词表封闭仍成立） | T03 schema 修订 |
| **G-05** | requirements 与骨架冲突（"bedroom faces_south" vs 北带卧室）无仲裁点 | 素材 A | **设计点**：冲突在 S1 由主 agent 裁决（调整骨架或标注 requirements 例外），rooms 不硬扛；走查记录进 prompts/orchestrator/skeleton.md（W5） | T06 记录 → W5 prompts |
| **L-01** | 弧面房间不是等宽矩形（on_edge 的 w_m 是直线深度） | 素材 B | **部分解决（D27）**：新增 `polygon` 第五形式（轴网索引顶点 + arcs 复用 aiplan），L 形/凹形/弧面房间可直接表达；on_edge 的 w_m 直线近似仅剩沿边矩形场景；布尔组合（union/subtract）列为 O7 后续增强 |
| **L-02** | special_openings 与 holes 语义分工不清 | 素材 C | **标限制**：holes=真实孔洞（建筑物理）；special_openings=吊装/设备孔（施工需求，at_axes 标注） | W1 实现时文档澄清 |

**结论**：4 个 schema 缺口（G-01~G-04，全部转 T02/T03 修订）+ 1 个设计点（G-05，转 W5 prompts）+ 2 个限制（L-01/L-02）。
真实住宅 + 三极端轮廓**全部可表达**（缺口已全部转化为 schema 修订，无不可表达的硬伤）。
**更新（2026-08-10 D27）**：L-01 弧面/L 形经新增 `polygon` 第五形式部分解决——轴网索引顶点 + arcs 达到 aiplan ring 表示水平；布尔组合留 O7。

## 7. 走查附加发现（进 W1/W2 实现注意）

- **on_edge 沿边排序**：`after:<room_id>` + `w_m` 是沿边带排布的两维（轴向位置 + 深度），normalizer 需支持"沿边队列"解析——W1 normalize 核心逻辑。
- **多 footprint 块房间归属**：garage 落在 outline_mm[1]，normalizer 的 R-01 检查按"房间多边形 ⊆ 所属块"判定，不跨块。
- **弧段定位**：openings 沿弧度量（along_m 沿弧），normalizer 需支持弧段长度参数化（arcAnn a0/a1）——W1 derive/normalize 注意。
