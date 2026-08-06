# 建筑词汇表（vocabulary)

> 生成建筑类 DXF 的**词汇边界**：构件与属性从本表取词，不造词。每个词附语义、参数与画法条目（archdxf_api.md 章节号）。

## 1. 开洞（外墙/隔墙通用）

| 词 | 语义 | 必选参数 | 可选参数 | 画法 |
|---|---|---|---|---|
| `door` | 门洞 | （所属墙， offset, 宽度）, swing | 高度（注记用） | api §3 door_leaf |
| `window` | 窗洞 | （所属墙， offset, 宽度）, sill | 高度、egress | api §3 window_line |

约束：door 无 sill、window 无 swing（字段互斥）;`offset + 宽度 ≤ 墙长`（几何校验）。

## 2. 门 swing 四值

| 值 | 铰链端 | 开向 |
|---|---|---|
| `in-left` | 低偏移端 | 向墙内侧（+d) |
| `in-right` | 高偏移端 | 向墙内侧（+d) |
| `out-left` | 低偏移端 | 向墙外侧（−d) |
| `out-right` | 高偏移端 | 向墙外侧（−d) |

用户语言→词汇换算：先说清"铰链在哪端、门往哪边开"，再查表取值。双开门、移门、卷帘门、地弹门为**扩展词**——画法未定前不得使用（登记于类型包）。

## 3. 墙

| 词 | 语义 | 声明方式 | 画法 |
|---|---|---|---|
| 外墙四向 | `front` / `rear` / `left` / `right`（面朝建筑看） | 矩形轮廓宽×深 + 墙厚 | api §1 rect_wall_frames + §3 wall_run |
| 隔墙 | 内部非承重分隔 | (axis `x`/`y`, offset, from, to, thickness) | api §1 partition_frame + §3 wall_run/end_cap |

## 4. 洁具与设备（10 型）

| 词 | 中文 | 参数 | 画法 |
|---|---|---|---|
| `toilet` | 坐便器 | at, rotation | api §4 |
| `lavatory` | 洗手盆 | at, rotation | api §4 |
| `bathtub` | 浴缸 | at, rotation | api §4 |
| `shower` | 淋浴间 | at, rotation | api §4 |
| `kitchen-sink` | 厨房水槽 | at, rotation | api §4 |
| `range` | 灶台 | at, rotation | api §4 |
| `refrigerator` | 冰箱 | at, rotation | api §4 |
| `washer-dryer` | 洗烘组合 | at, rotation | api §4 |
| `water-heater` | 热水器 | at, rotation | api §4 |
| `counter` | 台面 | at, rotation, **size 必填** | api §4 |

rotation ∈ 0/90/180/270(CCW,0 时背部朝 +y 即贴北墙）。

## 5. 消防探测

| 词 | 符号 | 参数 | 画法 |
|---|---|---|---|
| `smoke` | 圆+S | at | api §5 detector_symbol |
| `co` | 圆+CO | at | api §5 detector_symbol |
| `combo` | 圆+S/CO | at | api §5 detector_symbol |

## 5b. 楼梯（多层建筑预留）

| 词 | 语义 | 必选参数 | 可选参数 | 画法 |
|---|---|---|---|---|
| `stair-flight` | 楼梯跑段（多层平面必须预留的空间） | at, length, width | tread(默认 280), going(`up`/`dn`，默认 up), rotation | api §4b draw_stair_flight |
| `stair-landing` | 楼梯平台 | at, width, depth | rotation | api §4b draw_landing |

约束：
- **多层建筑平面必须为楼梯间预留空间**——跑段+平台的几何占位是疏散与垂直交通的图形证明，缺位即方案不成立；
- 多跑楼梯 = 镜像跑段 + 平台**组合声明**（双跑示例见 api §4b);
- 踏步几何（tread 常规 250–300）只查 `0 < tread ≤ length`；踏步级数、净空、疏散宽度标 BY REVIEW;
- 楼梯间落位（贴核心筒/外墙）属类型包范围声明，不在通用词层强制。

## 6. 标注元素

| 词 | 语义 | 画法 |
|---|---|---|
| 开洞链 | 角→jamb→jamb→角站点序列 | api §5 dim_chain |
| 总尺寸 | 轮廓总体尺寸，恒在 front+left，有开洞的侧面加一道 | api §5 add_dim |
| 门窗编号 | 同规格归组 D1/D2…、W1/W2… 圆标 | api §5 add_tag |
| 房间名 | 大写+下划线+面积小字（面积 STATED) | api §5 room_label |
| 引线标注 | 拥挤构件的避让标注 | api §5 add_leader |
| 指北针 | rotation 由用户给定，缺省不画 | api §5 north_arrow |
| 剖切符号 | split bubble+方向三角 | api §5 section_bubble |
| 图题 | 下划线标题+SCALE 行 | api §5 view_title |

## 7. 单位与格式

| 约定 | 值 |
|---|---|
| 单位 | 图形内唯一（mm 或 ft)，脚本头部声明 |
| 标注文本 | mm → 整数；ft → 英尺-英寸 1/16" 精度（api §5) |
| 文本 | 标注与房间名全大写 |
| 图层 | AIA 命名，按图域取表（api §6) |
