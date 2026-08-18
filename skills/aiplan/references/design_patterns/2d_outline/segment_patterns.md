# segment_patterns —— projection / recess / arc · 金例吸收版

> segments 表达「在真实轮廓直边上附加的规则凹凸/圆角」——**主体必须是真实形态的
> 多顶点折线**（斜墙/切角/天井/户型凹凸写进边），segments 只补「规则凸出」这类
> 可用参数化表达的细节。**主体必须已是真实形态的多顶点折线**（斜墙/切角/错位
> 直接写进边）——参考 res_3c6u 改写（2026-08-17）：真实 20 顶点直写四边，
> 核筒凸出/阳台带是轮廓本身的一部分，segments 只做规则细节的参数化补述。

## pattern: projection_on_edge（规则凸出）

**适用**: 南向连续阳台带、规则核筒外凸——近正交，可用 offset/width/depth 描述。
**要点**: `at_edge` 为展开后外法向方位；offset 从该边起点沿边计量（米）。
同边多个 projection 的 offset+width 区间**互不重叠**（重叠 → normalize 报 segment_overlap）。

```json
"segments": [
  {"type": "projection", "at_edge": "N", "offset_m": 6.2, "width_m": 5.3, "depth_m": 2.8, "note": "east核筒外凸(x44~49.3m 深2.8m)"},
  {"type": "projection", "at_edge": "N", "offset_m": 21.1, "width_m": 13.8, "depth_m": 3.0, "note": "mid核筒外凸(x20.7~34.5m 深3.0m)"},
  {"type": "projection", "at_edge": "N", "offset_m": 44.1, "width_m": 5.3, "depth_m": 2.8, "note": "west核筒外凸(x6.2~11.5m 深2.8m)"},
  {"type": "projection", "at_edge": "S", "offset_m": 2.4, "width_m": 50.7, "depth_m": 0.95, "note": "南侧6户连续阳台带凸出0.95m"}
]
```

参数来源：`residence/res_3c6u_std` 真实轮廓（已直写进边，2026-08-17 改写）——
核筒凸出 depth 2.8~3.0m、阳台带 depth 0.95m 是真实量级。segments 表达的是这类
「规则凸出」；若形态不规则（斜墙/天井/错位）则直接写进边多顶点，不走 segments。

**教学要点**：
- 核筒凸出 → projection at N/S（住宅核筒靠外墙凸出井道）
- 连续阳台带 → 一条宽 projection（width ≈ 整户面宽带，depth ≈ 0.9~1.0m）
- 错层露台/转角阳台 → 分段 projection（每段对应一户/一组户，offset 错开）
- **反例**：斜边硬套 projection（外法向不是 N/S）；凸出已在边内大折画了又重复；
  边仅 2 点 + 等分投影带冒充户型轮廓（= 没表达户型错位/转角/进深差异）

---

## pattern: arc_fillet_corners（角点真弧）

**适用**: 幕墙/窗墙圆角（酒店四角、商场转角）——**真实存在的弧，不臆造**。
**要点**: `type=arc` + `at_vertex`（拼合并 CCW 之后的下标）+ `radius_m`。
多弧从大下标做到小下标；normalize 移位 `arc.at` 供 densify。半径来自 source ARC。

```json
"segments": [
  {"type": "arc", "at_vertex": 0, "radius_m": 4.5, "note": "西南"},
  {"type": "arc", "at_vertex": 1, "radius_m": 4.5, "note": "西北"},
  {"type": "arc", "at_vertex": 2, "radius_m": 4.5, "note": "东北"},
  {"type": "arc", "at_vertex": 3, "radius_m": 4.5, "note": "东南"}
]
```

金例：`hotel/hotel_std_01`（四角 r=4.5m）、`retail/retail_mall_01`（转角 r=15.1/15.1/13.8/11.0m——
商场转角半径大，跟随幕墙真实圆弧）。
**反例**: 用密折线冒充圆角；半径 ≥ 邻边 → arc_fillet_failed；无弧却编弧。
