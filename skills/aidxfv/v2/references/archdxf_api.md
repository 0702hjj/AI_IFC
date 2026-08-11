# archdxf API 参考（文本镜像）

> 本文件是 `scripts/packages/archdxf/` 库的**唯一调用依据**。写 gen_dxf() 前必读；库改 API 本文件必同步改。
> 单位约定：库单位无关——所有长度/字高/半径用**图形单位**(mm 图给 mm,ft 图给 ft)。洁具符号内置毫米行业标准尺寸，英尺图须按比例换算或自绘。
> 导入：`from archdxf import annotate, fixtures, frames, intervals, layers, openings`

## 1. frames — 局部坐标系

### `frames.WallFrame(origin, s_dir, d_dir, length)`
墙的局部坐标架：`s` 沿墙（从该墙偏移原点起算）,`d` 跨墙厚（内正，外饰面 d=0)。
- `.point(s, d) -> (x, y)` 局部→平面
- `.angle(local_degrees) -> float` 局部角→平面角（用于弧线起止角）

### `frames.rect_wall_frames(width, depth) -> dict[str, WallFrame]`
矩形轮廓四面外墙的 frame 表，键 `"front"/"rear"/"left"/"right"`。建筑局部系：原点在轮廓前左角，x 沿宽，y 向后。偏移量起算：front/rear 从左端，left/right 从前端。

```python
fw = frames.rect_wall_frames(8000, 6000)
fw["front"].point(1000, 0)   # (1000.0, 0.0)
```

### `frames.partition_frame(axis, offset, thickness, length) -> WallFrame`
隔墙 frame。d=0 在负侧，使 `"in"` swing 朝正侧开启。

### `frames.SymbolFrame(msp, at, rotation_degrees=0, layer="A-FIXT")`
符号局部系（中心原点、背朝 +y、CCW 旋转），带五原语：
- `.point(x, y)` / `.rect(cx, cy, w, d)` / `.line(x1, y1, x2, y2)` / `.circle(cx, cy, r)` / `.ellipse(cx, cy, rx, ry)` / `.label(text, height, cx=0, cy=0)`

## 2. intervals — 区间相减

### `intervals.subtract_intervals(span, cuts) -> list[Interval]`
`span − cuts → 剩余段列表`（有序）。墙面线、填充、尺寸链**必须共用同一份 cuts**，断口才对齐。

## 3. openings — 开洞构造

构造顺序固定：**面 → 减去开洞 → jamb 封口 → 符号**。

### `openings.wall_run(msp, frame, span, thickness, cuts, layer, *, inner_span=None, poche=True, hatch_span=None)`
画双面墙（两面都在 cuts 处断开）+ 实体 poché 填充。
- `inner_span` 缺省 = span 两端各内缩一个墙厚（外墙内面止于内角）；隔墙传与 span 相同。
- `hatch_span` 控制填充范围，用于**角部归属**（哪个朝向拥有角部由调用方声明，防重叠）。

### `openings.jamb_pair(msp, frame, s_start, width, thickness, layer)`
开洞两端跨墙厚封口线。每个开洞必画。

### `openings.door_leaf(msp, frame, s_start, width, swing, wall_thickness, layer="A-DOOR")`
90° 门扇线 + 1/4 圆摆弧。swing 四值：
| 值 | 铰链 | 开向 |
|---|---|---|
| `in-left` / `in-right` | 低/高 s 端 | 朝 +d 侧（墙内） |
| `out-left` / `out-right` | 低/高 s 端 | 朝 −d 侧（墙外） |

### `openings.window_line(msp, frame, s_start, width, wall_thickness, layer="A-GLAZ")`
窗 = 墙厚中线一条线。

### `openings.partition_end_cap(msp, frame, s, thickness, layer)`
隔墙自由端封口（端头不到其他墙时必画）。

### 完整开洞样例

```python
frame = frames.rect_wall_frames(8000, 6000)["front"]
cuts = [(1000, 1900), (4000, 5500)]              # 门 900 + 窗 1500
openings.wall_run(msp, frame, (0, 8000), 200, cuts, "A-WALL")
for s, w in cuts:
    openings.jamb_pair(msp, frame, s, w - s, 200, "A-WALL")
openings.door_leaf(msp, frame, 1000, 900, "in-left", 200)
openings.window_line(msp, frame, 4000, 1500, 200)
```

## 4. fixtures — 洁具符号

### `fixtures.draw_fixture(msp, kind, at, rotation=0, size=None, layer="A-FIXT", label_height=180)`
`kind ∈ fixtures.FIXTURE_TYPES`:`toilet` `lavatory` `bathtub` `shower` `kitchen-sink` `range` `refrigerator` `washer-dryer` `water-heater` `counter`。
- `at` = 符号中心；rotation 0 时背部（水箱/龙头/贴墙面）朝 +y,CCW 旋转。
- `size=(w, d)` **仅 counter 必填**，其余类型传了报错。
- 标准占地（mm):toilet 400×700、lavatory 550×450（椭圆）、bathtub 1700×750、shower 900×900、kitchen-sink 800×500、range 700×600、refrigerator 700×700、washer-dryer 1200×600、water-heater ∅400。

## 4b. stairs — 楼梯符号（方案级）

### `stairs.draw_stair_flight(msp, at, *, length, width, tread=280, going="up", rotation=0, layer="A-STRS", label_height=180)`
单个跑段：外框 + 平行踏步线 + 中部斜折断线 + 方向箭头与 UP/DN 字。
- 局部系：`at`=跑段中心，rotation 0 时跑向 +y("up"=向 +y 上行）;`going ∈ stairs.GOINGS`(`up`/`dn`)。
- 校验：`0 < tread ≤ length`、`width > 0`，违例报错。
- **多跑楼梯由调用方组合**：镜像跑段 + 平台。双跑示例：

```python
stairs.draw_stair_flight(msp, (-700, 0), length=3080, width=1200, going="up")
stairs.draw_stair_flight(msp, (700, 0), length=3080, width=1200, going="dn")
stairs.draw_landing(msp, (0, 2400), width=2600, depth=1200)
```

### `stairs.draw_landing(msp, at, *, width, depth, rotation=0, layer="A-STRS")`
平台：净矩形，与跑段的拼接定位由调用方负责。

## 5. annotate — 标注与符号

### `annotate.ensure_dimstyle(doc, name="ARCHDXF", *, text_height, arrow_size=None, offset_gap=None)`
建 ARCHTICK 斜 tick 标注样式（幂等）。文字在线上方、对齐读法；arrow/gap 缺省从字高推导。

### `annotate.add_dim(msp, p1, p2, *, angle, base, dimstyle="ARCHDXF", layer="A-ANNO-DIMS", text=None, unit="mm")`
线性标注；`base` 定标注线位置。`unit="mm"` → 整数文本；`unit="ft"` → 英尺-英寸 1/16" 精度（`format_dim_feet_inches`)。`text` 显式给则覆写。

### `annotate.dim_chain(msp, stations, to_point, *, angle, base, dimstyle=..., layer=..., unit="mm")`
沿站点序列逐段标注（跳过零段）。开洞链站点 = `[墙起点, 洞1左, 洞1右, 洞2左, 洞2右, ..., 墙终点]`;`to_point` 例：`lambda s: frame.point(s, 0)`。

### 其余符号
| 函数 | 作用 |
|---|---|
| `add_tag(msp, mark, at, *, radius, text_height, layer)` | 圆标（D1/W1 类门窗编号） |
| `add_leader(msp, text, tail, target, *, height, layer, arrow=None)` | 引线标注；文字在 tail 侧避让，箭头双翼 20° 落 target |
| `underlined_text(msp, text, at, *, height, layer)` | 居中文字+下划线 |
| `room_label(msp, name, at, *, height, area=None, area_text=None, area_height=None, layer)` | 房间名：大写+下划线，面积小字在下（面积 STATED，不计算） |
| `detector_symbol(msp, kind, at, *, radius, text_height, layer="A-FIRE")` | 烟感/CO:kind ∈ `smoke/co/combo`，圆+S/CO/S/CO 字 |
| `view_title(msp, title, at, *, height, scale_label=None, scale_height=None, layer)` | 图题：下划线标题+（可选）SCALE 行 |
| `north_arrow(msp, at, *, size, rotation_degrees=0, layer)` | 指北针：圆+实心指针+N,CCW 转角 |
| `section_bubble(msp, name, sheet, center, direction, *, radius, text_height, layer="A-ANNO-SECT")` | 剖切符号：split bubble（字母/图纸号）+实心三角指向 |

## 6. layers — 图层表

### `layers.ensure_layers(doc, table)`
`table` 为表名或显式 dict。表名 ∈ `layers.LAYER_TABLES`:`floor` `site` `section` `elevation` `roof_plan` `schedule` `foundation` `framing`（各带 AIA 命名+色/线宽/线型）。幂等，已存在跳过。

## 7. 确定性配方（字节级重现）

```python
ezdxf.options.write_fixed_meta_data_for_testing = True  # 钉元数据
doc = ezdxf.new("R2010", setup=True)
```

保存后（CLI 落盘之外）做一次 CLASSES 段规范化——ezdxf 的 CLASSES 注册序随进程哈希随机化，不规范化则同输入也可能 diff 非空：

```python
from archdxf.canon import canonicalize_dxf
canonicalize_dxf("output.dxf")   # 排序 CLASSES 段,几何不变,CAD 读取器忽略该序
```

同输入重生成 + canon 后应 diff 为空（金样验收项）。
