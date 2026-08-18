# skeleton.md —— 主 agent S1 骨架设计规范

## 工作流（底座先行）

S0 preprocess 已机械生成底座 `derived/skeleton_base.json`，从底座出发填充：

- `zones[].outline`：plan outline_mm **原样注入**（坐标根基，多块/真弧/孔洞）
- `zones[].core.anchor`：plan core_anchor_mm **锁死注入**（多核已拆成带 id 数组）
- `frame`：从 plan site 继承（origin/north_deg/modulus 缺省 300）

你在底座上全权填充修改：补 typology / typology_reason / core vertices（或
path 分段）/ corridor / main_partitions / blocks，也可调整底座任何字段。
底座的意义是**坐标源头唯一**——从对的起点出发。

## 设计方法（分层外推，机器差集）

**骨架 = 空间分层的语义表达**——你说每层的形状/边界，机器做差集/切割：

```
层级外推（你声明，机器算）：
  ① core       vertices 平铺顶点环 × N（多核各带 id；分段语义走 path ring_edges）
  ② corridor   外缘闭合线（ring_edges 分段）——区域 = 外缘 − 核（机器差集自动）
  ③ 大区       outline − corridor 环 = 大区（机器差集自动）
  ④ main_partitions 切割线（锚定内外边界）→ 大区切段
  ⑤ blocks     每段声明类型（between 引用切割线认领段，CD 交叉排列）
```

**形态族兼容**（按 building_types 选，覆盖全部类型）：
- **A 单内环+环带**（office/retail）：core → corridor 环带（ring_edges 分段）→ 环带大区
- **B 带形走廊**（hotel 双内廊）：corridor 用 path 分段表达（多 core 环绕也走 path 分段——外缘轮廓分段，机器 union 多核并集后差集 = 走廊带）
- **C 多核无走廊**（residence）：分层外推但 corridor 可空（core 直接到大区）
- **D 无核独立块**（single_family）：blocks 独立声明（无 core/corridor）

**轴网派生**：轴网由机器从分区边界线提取（粗，分区级参照）——机器派生。

## path 分段写法（ring_edges 四边拼合 + segments，对齐 aiplan）

```jsonc
// 核心筒（anchor + vertices 平铺顶点环——绝对坐标继承 plan core，锚点锁死；
// 分裂闭合分段需 segments 语义时改用 path ring_edges 四边拼合）
"core": [
  {"id": "c0", "anchor": [12000, 12000],
   "vertices": [[8000,8000],[16000,8000],[16000,16000],[8000,16000]]},
  {"id": "c1", "anchor": [30000, 12000],
   "vertices": [[26000,8000],[34000,8000],[34000,16000],[26000,16000]]}
]

// 走廊外缘（ring_edges 分段 path 表达，机器差集 − 核 = 走廊带）
"corridor": {
  "form": "path", "width_mm": 2400,
  "path": {
    "edges": {
      "west":  [[6000, 6000],  [6000, 18000]],       // 西南角→西北角
      "north": [[6000, 18000], [18000, 18000]],      // 西北角→东北角
      "east":  [[18000, 18000], [18000, 6000]],      // 东北角→东南角
      "south": [[18000, 6000], [6000, 6000]]         // 东南角→西南角
    },
    "segments": [
      {"type": "recess", "at_edge": "W", "offset_m": 6.0, "width_m": 6.0, "depth_m": 1.5},   // W 边凹进（入口门廊）
      {"type": "projection", "at_edge": "S", "offset_m": 3.0, "width_m": 4.0, "depth_m": 2.0}, // S 边凸出（阳台）
      {"type": "arc", "at_vertex": 0, "radius_m": 4.5}                                        // 顶点倒圆角
    ],
    "holes": []                                        // 孔洞（同 edges 格式）
  }
}

// 切割线（锚定内外边界——from/to 是 {ref, edge?, at} 对象，坐标机器算）
"main_partitions": [
  {"id": "cut:0", "role": "radial",
   "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},   // 走廊外缘北边中点
   "to": {"ref": "outline:edge:2", "at": 0.5}},                 // 轮廓北边中点
  {"id": "cut:1", "role": "radial",
   "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
   "to": {"ref": "outline:edge:0", "at": 0.5}}
]

// blocks（切割线围成的段——between 引用切割线 id，side 消歧多候选段）
"blocks": [
  {"id": "b_east", "role": "open_office",
   "between": ["cut:0", "cut:1"], "side": "E"},
  {"id": "b_west", "role": "units",
   "between": ["cut:0", "cut:1"], "side": "W"}
]
```

**切割线/blocks 语义**：
- 切割线 `{id: "cut:N", role, from: {ref, edge?, at}, to: {ref, edge?, at}}`：
  - ref 词表：`corridor:outer`（走廊外缘）/ `outline:edge:<N>`（轮廓第 N 边）/ `core:<id>` / `hole:<N>`
  - `edge`（N/S/E/W）：ref 是多边闭合线时指定哪条边（outline:edge:N 已隐含，可省）
  - `at`：沿边比例位置（0-1，缺省 0.5 中点）
  - 机器算两点 → 绝对坐标线段 → shapely split 切大区
- blocks `{id, role, between: [cut ids], side?}`：
  - 机器切段后自动编号；between 找边界触两切割线的段
  - 唯一 → 认领；多个候选 → `side`（8 方位，质心相对走廊质心）消歧
- 切割线必须**径向穿透**大区（内边界到外边界）才能切开——两条竖线切成东西两块

**分段语义**：
- `edges.{west,north,east,south}`：四条边折线拼合成闭合环（角点共享：west 末点=north 首点=西北角…）——模型说"哪条边往内/往外/带弧"（segments），坐标机器算
- **segments 三型**（米制参数）：
  - `recess`：`{at_edge: N|S|E|W, offset_m, width_m, depth_m}`——凹进（入口门廊/采光井）
  - `projection`：同 recess 参数——凸出（阳台/凸窗）
  - `arc`：`{at_vertex: 顶点下标, radius_m}`——顶点倒圆角
- **arc**：圆角/弧墙用 segments 的 arc 段（机器弦近似）
- 覆盖：core（vertices 平铺 ×N / path ring_edges）、corridor 外缘、大区分割线、blocks 段

## 端到端示例

`references/examples/layered_push_example.json` + `README.md`——完整链路演示：
skeleton 分层外推（本规范）→ 机器分区产物 → rooms 墙划分 → 机器房间产物。
同一案例从声明到机器产物的连贯对照（形态族 A 环带办公）。

## 决策槽位（每 zone ≤5 个决策）

按顺序设计，每槽位给 DSL 写法示例：

| # | 决策 | DSL 写法 |
|---|---|---|
| 1 | 形态族 | typology（A/B/C/D 按 building_types 选，typology_reason 引 geom 事实） |
| 2 | **外轮廓**（底座已注入——一般保持，确认分区以此为界即可） | `"outline": [{"outer": {"vertices": [[x,y],...], "arcs":[...]}, "holes": [...]}]`——多块分区轮廓（绝对坐标，真弧/孔洞），骨架分区以此为界（越轮廓 error） |
| 3 | 核心筒 | `"core": [{"id":"c0","anchor":<底座锁死>,"vertices":[[x,y],...]}, ...]`——vertices 平铺顶点环 ×N（凸字形等非矩形筒）；分段语义（segments 凹进/凸出/圆角）走 `path` ring_edges 四边拼合 |
| 4 | 走廊（ring_edges 分段） | `"corridor": {"form": "path", "path": {edges + segments}, "width_mm":...}`（无走廊 → null，形态族 C/D） |
| 5 | 切割线 + blocks | `"main_partitions": [{"id":"cut:0","from":{"ref":"corridor:outer","edge":"N","at":0.5},"to":{...}}]` + `"blocks": [{"id":"b0","role":"...","between":["cut:0","cut:1"],"side":"E"}]`（role 取类型包 block 词表） |

## 读图方法（geom 派生字段逐个怎么读）

- **edges**：边的方位/长度 → 哪面朝南（采光分配的事实基础）
- **concave_corners**：凹角在哪 → 形态心智模型（L 形/带台阶）
- **deep_zone**：暗区占比/区域 → 走廊/核心/贮藏该放哪
- **core_anchor 语境**：锚点偏哪 → 主功能块往哪摆
- **strip_area**：每米轴跨面积 → 配比翻轴跨的换算尺

## 五考验点自查清单（Q1-Q5）

- [ ] **Q1 形状读解**：typology_reason 必须引用 geom 事实（"因 holes[0] 居中故环绕"）
- [ ] **Q2 面积换算**：area_allocation 配比 → 分区容量（用 strip_area 估算）
- [ ] **Q3 锚点语境**：核心筒偏置 → 东北完整大板的主功能分配
- [ ] **Q4 暗区处置**：deep 区 → 走廊/核心/贮藏的功能匹配
- [ ] **Q5 跨 zone**：交接面共享边两侧 partition 对齐

## 留痕

- `typology_reason` **必须引用 geom 事实**（edges/凹角/holes/deep_zone 字段名）
- `note_responses` 逐条响应 plan 的 note
- `case_ref`（参照了哪个金例）或 `from_scratch`（无参照）

## 金例参照（goldlib 检索）

**骨架设计前/卡住时用 goldlib 检索**：

```
# 骨架抽象模式（类型特化方法）——按痛点检索
aidxfv3 gold query --project <golden.db> --params '{"kind":"pattern","pain":"P1-x","type":"<zone function>"}'

# 案例骨架 DSL 封装（真实案例的骨架具体怎么写）——按类型拿完整案例
aidxfv3 gold query --project <golden.db> --params '{"kind":"case","type":"<zone function>"}'
#  → 返回 case.skeleton_dsl（core/corridor/main_partitions/blocks 真实写法，可改参数套用）
```

- **抽象模式**（`--kind pattern`）：学"这类型骨架一般怎么搭"（板式/环廊/中庭…）
- **案例封装**（`--kind case`）：学"这个真实案例的骨架具体用 DSL 怎么写"——`skeleton_dsl` 是可照抄改参数的完整骨架声明
- golden top-2 整体参照时机：形态把握不准时（完整案例含 outline/rooms/墙门窗）

## 呈现格式（断点①给用户的一句话摘要）

```
骨架设计完成（<zone> 段）：形态族 <A/B/C/D>，核心筒 <n> 个 <位置>，走廊 <形式>，
校验 <通过/error>，待确认项: <1-2 项>
```
