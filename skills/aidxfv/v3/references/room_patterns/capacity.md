## pattern: 住宅功能优先级（B_原始结构图实测）
命中痛点: P2-4
适用条件: {"priority_check": true}
案例来源: B_原始结构图.dxf

设计要点（排布优先级）:
  1. 南侧采光起居：客厅+阳台（采光面优先给起居）
  2. 北侧管线区：厨卫+餐厅（管线集中）
  3. 安静侧：卧室/主卧/书房（远离起居动线）

DSL 片段（节选自 golden/residence/res_2s4u_std/rooms.std.json——户型角部房间组，
按优先级分区画墙贴标签；房间组 11.1㎡ 卧室 + 4.5㎡ 湿区小间）:
  "partitions": {"south_wing": "outline"},  // res_2s4u 现盘无 block 认领，角部屋落 outline
  "walls": [
    {"key": "1F:int:8", "kind": "int", "t_mm": 120,
     "axis": [[-2931, 840], [-2931, 4090]]},
    {"key": "1F:int:13", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4090], [-2881, 4890]]},
    {"key": "1F:int:14", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4890], [-181, 4890]]}
  ],
  "labels": [
    {"room": "space_8", "type": "bedroom", "area_sqm": 11.1,
     "at": [-1551, 2859]},
    {"room": "wet_a", "type": "bathroom", "area_sqm": 4.5,
     "at": [-1896, 3724]}
  ]

决策依据: 真实案例——采光面给起居、管线区给厨卫、私密/安静给卧室。
反例: 先排贮藏 → 采光房塞不下 → R-03 面积 FAIL；厨房占南侧 → 采光面浪费。

## pattern: 塞不下走 infeasible
命中痛点: P2-4 / P2-5
适用条件: {"over_capacity": true}

DSL 片段（rooms.json 直通申报形态——schema 保留）:
  {"floor": "<层>",
   "status": "infeasible",
   "region": {"x": [...], "y": [...]},
   "reason": "面积缺口 <N>㎡",
   "evidence": {"required_sqm": <program 合计>, "available_sqm": <实测>}}

决策依据: 分区内不可解 → 申报，不硬塞不造假（R-03 面积造假即 error）。
反例: 硬塞 → 面积声明与实测不符 → R-03 error + reconcile error 双拦。
