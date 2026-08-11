# Plan 落盘契约（plan → cad → bim 衔接格式）

管线三个阶段的**唯一事实源是落盘文件**，不是会话记忆。AGENT 每次开工统一加载
plan 落盘，完成 cad 阶段后写出 building.json + DXF 集。任何阶段的修正通过改
落盘文件生效，重跑即采纳。

## 1. plan.json —— plan 阶段产物，cad 阶段输入

```json
{
  "version": 1,
  "project": "string",
  "building_type": "office | retail | residence | adu | custom",
  "site": {
    "lot_width_mm": 15000,
    "lot_depth_mm": 20000,
    "setbacks_mm": {"front": 0, "rear": 0, "left": 0, "right": 0}
  },
  "floors": [
    {"name": "1F", "height_mm": 3600, "usage": "lobby + open office"}
  ],
  "program": {
    "area_target_sqm": 0,
    "rooms": [{"name": "meeting", "count": 2, "area_sqm": 20}],
    "notes": "free text, untrusted intent hints"
  },
  "constraints": {
    "max_footprint_sqm": 0,
    "accessibility": false,
    "custom": {}
  },
  "draft": null,
  "confirmed": false
}
```

规则：
- `building_type` / `site` / `floors` 是 cad 阶段的**硬约束**；`program` 是意图，
  cad 可在 step1 草案中重排，但必须在 step2 向用户说明偏差。
- `draft` / `confirmed` 由 cad 阶段写回（见 §3 状态机），plan 阶段一律留初值。
- 缺失字段处理：硬约束缺失 → cad step0 停步并向用户索取；意图缺失 → step1 用
  类型包默认值补全并在草案中标注"默认"。

## 2. building.json —— cad 阶段产物，bim 阶段输入（最小集）

```json
{
  "version": 1,
  "project": "string",
  "floors": [
    {
      "name": "1F",
      "dxf": "1F.dxf",
      "elevation_mm": 0,
      "height_mm": 3600,
      "sha256": "hex of the canonical dxf"
    }
  ],
  "metadata": {
    "materials": {},
    "occupancy": "string",
    "non_geometric_notes": "DXF 承载不了、bim 建模需要的建筑信息（材质/构造做法/设备）"
  }
}
```

规则：
- `dxf` 为相对 building.json 所在目录的路径；所有 DXF 必须过 archdxf canon。
- `sha256` 在 canon 之后计算，bim 阶段据此校验图纸未被手工改。
- DXF 不承载的信息（层高、材质、竖向标高关系）**必须**写进 building.json，
  不许口头传递。

## 3. cad 阶段状态机（写在 plan.json 上）

| 状态 | 标志 | 下一步 |
|---|---|---|
| 待草拟 | `draft: null, confirmed: false` | step1 草拟 |
| 待确认 | `draft: {...}, confirmed: false` | step2 交互确认 |
| 已定稿 | `confirmed: true` | step3 构建（draft 冻结为硬约束） |

中断恢复：重跑 step0 重新加载 plan.json，按上表路由，不依赖任何会话上下文。
