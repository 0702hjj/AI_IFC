# 端到端示例：分层外推分区 → 分区内画墙房间（30×30m 环带办公层）

> 本目录的 `layered_push_example.json` 是**完整链路演示**——同一个案例从
> skeleton 分区声明 → 机器分区产物 → rooms 墙声明 → 机器房间产物。
> 模型写骨架/房间拿不准时读这份示例（声明长什么样、机器算出什么）。

## 链路总览（形态族 A：环带办公）

```
① skeleton DSL（模型声明）
   outline 30×30（底座注入）
   core 10×10 居中（vertices 绝对坐标）
   corridor 外缘 20×20（ring_edges 四边拼合）——机器差集出走廊带
   main_partitions 2 条径向切割线（from/to 锚定：走廊北边中点→轮廓北边中点）
   blocks 东西两块（between 引用切割线 + side 消歧）
        ↓ normalize_skeleton（机器）
② 机器分区产物
   corridor_zone = 20×20 − 10×10 = 300㎡（走廊带）
   big_zones = 30×30 − 20×20 = 500㎡（大区）
   cuts = 2 条绝对坐标线段
   blocks = 东西各 250㎡（shapely split 切段 + between 认领）
   axis_grid_derived / partition_labels（机器派生）
        ↓
③ rooms DSL（模型声明——东块内画分墙）
   partitions 承接 block:b_east
   walls 两道竖分墙（绝对坐标）
    labels 两个房间（at 落区绑定）
    ——门窗在 details 阶段（D44 归 details）
         ↓ normalize_rooms（机器）
 ④ 机器房间产物
    walls = 绝对坐标墙线段
    rooms = office_01（80㎡，贴东外墙 frontage:E）+ meeting_01（250㎡）
    neighbors = 共享墙推导（office_01 ↔ meeting_01）
    boundary_walls = 每房间围合墙段（details 开洞依据）
```

## 关键观察（学这份示例看什么）

1. **模型声明里没有分区多边形/房间多边形**——分区是机器差集+切割出来的，
   房间是墙围出来的；声明只有语义（分段/锚定/墙段/标签点）
2. **切割线必须径向穿透**（内边界→外边界）——2 条竖线把大区切成东西两块；
   单条线切开环带无效（annulus 拓扑）
3. **between 多候选用 side 消歧**——东西两块都触 cut:0/cut:1，side:E/W 区分
4. **房间面积是机器实测**——label 的 area_sqm 是目标（R-03 ±10% 校验），
   polygon_mm.area_sqm 是机器从墙围区域算的
5. **门窗在 details 阶段**——details 阶段按统一规律沿墙定位（boundary_walls 给墙在哪）

## 与金例的关系

- 金例 `references/golden/*/rooms.std.json` = 真实图纸的墙划分（第三步的真实版）
- 金例 `references/golden/*/skeleton.json` = 骨架协议（切割线锚定+between：
  core vertices 平铺、corridor ring_edges），声明层示例以本文档为准
