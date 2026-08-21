# draw_api.md —— dxfkit.draw 函数清单（LLM 逐构件调用面）

> 画 DXF = LLM 逐构件调 dxfkit.draw。本清单是模型画图时的手册：一次调用一个构件，
> 画法是你的决定（门 swing/避让/对齐/标注）。

## 画图流程总览

```
⓪ record.start() + record.wrap_draw_module(draw)   # 开记录（机器固化 build() 脚本用，draw_api 不变）
① new_doc() 建文档（R2010 + mm + 图层表 + 标注样式，AutoCAD 兼容）
② draw_partition_base() 画分区轮廓底座（skeleton normalize 产物：outline/core/corridor/切割线）
③ 逐构件画：墙 → 开洞 → 门/窗 → 楼梯/构件 → 标注/尺寸/标签
④ doc.saveas() 存盘（中文自动转 \U+XXXX + 字节级确定）
⑤ record.to_build_script(record.calls(), params)    # 固化 build() 脚本（该 zone 构建脚本事实源）
```

> **record 记录（2026-08-21 起，draw_api 能力规范不变）**：画图前 `record.start()` +
> `record.wrap_draw_module(draw)` 开启——机器在 draw 实现侧记录每次调用（函数+参数+次序），
> 画完 `record.to_build_script(record.calls(), params={skeleton/rooms/details DSL})` 固化为
> archdxf 可运行的 **build() 脚本**（该 zone 构建脚本事实源，供 S4-b 注册平台模型）。
> key 顺序计数确定性（reset_keys 归零，同序列重放产同 key）→ 固化脚本重放 = 原图（字节级）。
> 详见 `draw_composition.md` 第 5 步 + `machine_contract.md` S4 交付改造。

## 函数清单

### 文档

| 函数 | 签名 | 用途 |
|---|---|---|
| `new_doc` | `new_doc(units="mm") -> Drawing` | 建文档。返回的 doc 存盘自动 ASCII 转义中文 + 字节级确定 |
| `canonicalize` | `canonicalize(path)` | 确定性配方（CLASSES 段排序，字节级重现） |
| `reset_keys` | `reset_keys()` | 清空墙 key 注册表（每层画图前调用） |

### 分区底座（D37/D40）

| 函数 | 签名 | 用途 |
|---|---|---|
| `draw_partition_base` | `draw_partition_base(msp, geom) -> {n_outline, n_core, n_corridor, n_cut}` | 按 normalize 分区几何画底座 DXF（WALL 层：outline+core+corridor 外缘+切割线） |

### 墙与开洞（核心链）

| 函数 | 签名 | 用途 |
|---|---|---|
| `wall_run` | `wall_run(msp, p0, p1, thickness, cuts, hatch_span=None) -> wall_key` | 画一段墙（p0→p1 轴线），返回墙 key（**记入沿墙定位 registry**，openings 挂它） |
| `opening` | `opening(msp, wall_key, at_or_along, width_mm) -> str` | 墙上升洞（jamb 对穿墙厚） |
| `door` | `door(msp, wall_key, open_key, at_or_along, width_mm, ...) -> str` | 门（leaf + swing 弧沿墙定位） |
| `window` | `window(msp, wall_key, at_or_along, width_mm) -> str` | 窗（窗线沿墙居中） |
| `partition_cap` | `partition_cap(msp, wall_key, at_or_along) -> str` | 分墙端头封口 |

### 楼梯/构件

| 函数 | 签名 | 用途 |
|---|---|---|
| `draw_stair` | `draw_stair(msp, at, size, run_width) -> str` | 楼梯 |
| `draw_landing` | `draw_landing(msp, at, *, width, depth) -> str` | 休息平台 |
| `draw_fixture` | `draw_fixture(msp, kind, at, rotation=0, size=None) -> str` | 洁具/设备（kind 按类型包词表） |
| `draw_column` | `draw_column(msp, at, *, size=700) -> str` | 柱 |
| `draw_detector` | `draw_detector(msp, kind, at, *, radius=300) -> str` | 探测器 |

### 标注/说明

| 函数 | 签名 | 用途 |
|---|---|---|
| `room_label` | `room_label(msp, name, at, area_sqm=None) -> str` | 房间名+面积标签 |
| `draw_dim_chain` | `draw_dim_chain(msp, wall_key, stations, angle=0.0, ...) -> str` | 尺寸链 |
| `draw_tag` | `draw_tag(msp, mark, at, *, radius=400, text_height=300) -> str` | 引出标签 |
| `draw_leader` | `draw_leader(msp, text, tail, target, *, height=300) -> str` | 引线注释 |
| `draw_north_arrow` | `draw_north_arrow(msp, at, *, size=800) -> str` | 指北针 |
| `draw_title` | `draw_title(msp, title, at, *, scale_label=None) -> str` | 图题 |
| `draw_section_bubble` | `draw_section_bubble(msp, name, sheet, center, direction=(0,1)) -> str` | 剖切符号 |

### 批量辅助（可选，仍逐构件内部执行）

| 函数 | 签名 | 用途 |
|---|---|---|
| `draw_rooms_model` | `draw_rooms_model(msp, model) -> dict` | 按 normalize 产物批量画（内部逐构件）——适合 rooms 整层 |
| `draw_windows_from_rooms` | `draw_windows_from_rooms(msp, rooms, window_w_mm=1500) -> int` | 批量窗（沿外墙） |

## 关键语义

1. **墙 key 沿墙定位**：`wall_run` 返回 key 并记入 registry（轴线+厚+方向）——`opening/door/window` 挂 key + 沿墙距离（at_or_along），任意方向墙（水平/竖直/斜/弧）都正确
2. **多段墙拆段**：normalize 把 polyline/path 墙拆成独立段——门窗挂哪段写哪段 key，along 从该段起点计
3. **图层**：墙 WALL / 门 DOOR / 窗 WINDOW / 楼梯 STAIR / 构件 FIXTURE / 柱 COLUMN / 文字 TEXT / 尺寸 DIM / 剖切 SECTION / 表格 TABLE / 屋顶 ROOF / 立面 ELEVATION（archdxf 层名已通用化）
4. **确定性**：`new_doc` 钉元数据 + `canonicalize` 排序——同一输入字节级同输出
