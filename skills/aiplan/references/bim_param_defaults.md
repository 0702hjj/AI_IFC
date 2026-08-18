# bim_param_defaults.md —— BIM 补充参数默认值表（aiplan 自持）

> aiplan 自包含纪律（P2）：本文件是 step-01 第 4 轮的**唯一参数来源**，
> 不读任何外部文档。roof 值域以自持 schema 为准；psets 默认值与
> `examples/bim_supplement_demo.json` 金样同源（改一处回查另一处）。
> 属性名对齐 IFC 标准 Pset（Pset_WallCommon / Pset_SlabCommon 等公开标准）。

## 1. roof 参数（值域 = bim_supplement.schema.json 自持约束）

| 参数 | 值域（schema 强制） | 常用默认 |
|---|---|---|
| `type` | gable / hip / shed / flat / freeform | gable |
| `slope_deg` | 25–45 | 35 |
| `ridge_h_m` | 1.5–4.0 | 2.5 |
| `overhang_m` | 0.3–0.6 | 0.4 |
| `dormer_count` | ≥0 | 0 |

## 2. psets 默认值（直落层，不弹框；回显一句"按类型标准默认"）

| 组 | 键 | 默认 | 说明 |
|---|---|---|---|
| building | `fire_protection_class` | `"Class 1"` | 耐火等级 |
| building | `sprinkler_protection` | `true` | 喷淋 |
| building | `occupancy_type` | 按 zone function（residential/office/retail） | 用途 |
| building | `number_of_storeys` | 由 floors 派生 | 层数 |
| walls | `fire_rating` | `"2h"` | 墙体耐火 |
| walls | `thermal_transmittance` | `0.35` | 外墙传热系数 U 值 |
| walls | `load_bearing` | `true`（外墙） | 承重 |
| slabs_roof | `pitch_angle_deg` | 同 roof.slope_deg | 屋面坡度 |
| slabs_roof | `thermal_transmittance` | `0.25` | 屋面传热 |
| slabs_roof | `fire_rating` | `"1h"` | 楼板耐火 |
| circulation | `fire_exit` | `true` | 疏散 |
| circulation | `required_headroom_mm` | `2100` | 净高 |
| circulation | `handicap_accessible` | `true` | 无障碍 |

**纪律**：用户明确给了值 → 用用户的；没给 → 本表默认直落，回显告知，不反对即落盘。
