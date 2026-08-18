# vertical_patterns.md —— 3D 空间排布 pattern（zone 间竖向关系）

> 管 **zone 间竖向组合与对齐**（`spatial_relations` + 跨层 core）。
> **2D 轮廓写法不在此文件**——以 `design_intent.schema.json`（`path.rings[].edges` + `segments`）
> 与 `references/golden/*` 金例为准。旧 `outer.base` 协议已废止，勿写。

---

## pattern: podium_tower（裙房 + 塔楼竖向分区）

**命中痛点**: PD-3  
**适用条件**: `multi_zone` 且 `buildable_area_sqm ≥ 1500`  
**适用场景**: 低层裙房满铺 + 高层塔楼收进上叠

**要点**（DSL 用 rings，非 outer.base）——zone 按**楼层范围**划分（2026-08-17 对齐协议）：
- **同楼层范围的多体量**（如同层两塔、多体量同层）→ **合并同一 zone，`rings` 数组多块**——
  每个 ring 独立四边，normalize → `outline_mm` 多块。同构/异构都不拆 zone。
- **异楼层范围**（裙房 1~4 层 + 塔楼 5~20 层）→ 不同 zone，塔楼楼层从裙房顶+1 起；
  竖向叠层用 `spatial_relations` `{"from":"tower","rel":"on","to":"podium","align":"..."}` 表达，
  normalize 按 align 落位；核心筒贯穿用 `core_stack_alignment`。
- 塔楼 outline ⊆ 裙房外环（normalize 落位后 `geom align` 校验）

**反例**: 同楼层同构两塔拆成两个 zone（应合并多 rings）；塔楼楼层从 1 起（应裙房顶+1）；
塔楼超出宿主 → `geom align` FAIL。

---

## pattern: core_stack_alignment（核心筒跨层对齐）

**命中痛点**: PD-3  
**适用条件**: multi_zone 且核心筒贯穿多层  

**要点**:
- 各 zone 的 `core.path.rings` 几何一致（同位置同尺寸）
- normalize 后 `geom align` 校验跨层 core shape
- 顶层机房缩小须 `zone_split`，不能静默改 shape

**反例**: 各层 core 漂移 → `geom align` FAIL。
