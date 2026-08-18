# draw_composition.md —— 整层 DXF 组装序（LLM 画图编排手册）

> 整层 DXF = 分区底座 + 逐构件增量。本文件是组装序——模型按序画，每一步是一次构件调用
> （画法是模型的自由：门 swing/避让/对齐/细部取舍）。

## 一条 DXF 链

```
skeleton.<floor>.dxf（分区轮廓底座，dxfkit 画）
      ↓ 复制
floor.dxf（rooms-worker 增量画）
      ↓ 复制
floor.dxf（details-worker 门窗统一规律 + 柱网 + 标注）——一条链不断裂，confirmed 后冻结
```

## 组装序（每层）

### 第 0 步：文档与底座

```python
from dxfkit.draw import new_doc, reset_keys, draw_partition_base, canonicalize
doc = new_doc()                      # R2010 + mm + 图层表
reset_keys()                         # 清墙 key 注册表
msp = doc.modelspace()
# 底座：normalize 分区几何（skeleton 侧产出）→ WALL 层轮廓
draw_partition_base(msp, skeleton_zone_geom)   # outline+core+corridor+切割线
```

### 第 1 步：墙（rooms normalize 产物的 walls[]）

```python
# 每道墙（line_mm 轴线多段）逐段画：wall_run 返回 key，记入沿墙 registry
for wall in rooms_model["walls"]:
    for seg in 每段(wall["line_mm"]):
        key = wall_run(msp, seg.p0, seg.p1, wall["t_mm"], cuts=该墙的开洞列表)
        # key 记入沿墙 registry——details 阶段门窗沿墙定位靠它
```

### 第 2 步：开洞 + 门窗（details 阶段）

```python
# 按 floor_details.md 统一规律批量：每房间 1 门挂公共区侧墙中点，
# 有 frontage 的房间在外墙中点开窗。墙在哪 = rooms_model["rooms"][i]["boundary_walls"]
for room in rooms_model["rooms"]:
    for bw in room["boundary_walls"]:
        # 门：共享内墙中点；窗：frontage 方位外墙中点
        door(msp, bw["key"], along_mm, width_mm, swing)   # 或 window(...)
```

### 第 3 步：楼梯/构件（labels 的 placemark + 类型包构件规则）

```python
for lab in labels_with_placemark:
    draw_stair(msp, lab["at"], size, run_width)      # stair
    draw_fixture(msp, kind, at, rotation, size)      # 洁具/设备
```

### 第 4 步：标注/说明

```python
for room in rooms_model["rooms"]:
    room_label(msp, room["id"], room["polygon_mm"]["centroid_mm"],
               area_sqm=room["area_sqm"])
draw_dim_chain(...)     # 尺寸链（关键开间）
draw_north_arrow(msp, at)
draw_title(msp, title, at)
```

### 第 5 步：封存 + 返回摘要

```python
doc.saveas("floor.dxf")   # new_doc 的 doc 自动 ASCII 转义中文 + 字节级确定
# 返回一行摘要——检查在主 agent 侧执行：
# 主 agent 回收后集中执行 readback + reconcile（一次对账）
# error 携报告（带 bbox 诊断）重派，按报告修
```

## 自由度与约束

| 自由（画法决定） | 约束 |
|---|---|
| 门 swing 开向 / 避让 / 对齐微调 / 细部取舍 | 房间划分保持（墙位置 = normalize 产物，reconcile 兜底） |
| 标注位置 / 尺寸链站点选择 | 逐构件画，逐构件调用画法库 |
| 构件尺寸/旋转（按类型包规则） | 门窗沿墙定位（墙 key + along） |

## 对账闭环

- **声明合法性 check**：声明段主 agent 跑一次（normalize 后）——声明未变即成立
- **底稿对账 readback + reconcile**：回收后主 agent 集中跑一次（worker 侧跑）
- svg 自检是 reconcile FAIL 时的可选诊断（报告已带 bbox）
