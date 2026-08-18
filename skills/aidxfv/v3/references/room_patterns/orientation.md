## pattern: 南侧起居+阳台（B_原始结构图实测）
命中痛点: P2-1 / P2-2
适用房间: living / balcony
适用条件: {"living_by_south": true}
案例来源: B_原始结构图.dxf（中国住宅）

设计要点: 客厅+阳台贴南分区外缘（采光起居）；阳台紧邻客厅南边（连续空间）。

DSL 片段（节选自 golden/residence/res_2s4u_std/rooms.std.json 真实落盘——户型角部 11.1㎡ 房间，
6 道墙 + 1 门 855mm，labels 落区绑定；南侧贴轮廓的房间组照此形制）:
  "partitions": {"south_wing": "outline"},
  "walls": [
    {"key": "1F:int:8", "kind": "int", "t_mm": 120,
     "axis": [[-2931, 840], [-2931, 4090]]},
    {"key": "1F:int:9", "kind": "int", "t_mm": 120,
     "axis": [[-181, 840], [-2931, 840]]},
    {"key": "1F:int:10", "kind": "int", "t_mm": 120,
     "axis": [[-2931, 4090], [-2881, 4090]]},
    {"key": "1F:int:13", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4090], [-2881, 4890]]},
    {"key": "1F:int:14", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4890], [-181, 4890]]},
    {"key": "1F:int:22", "kind": "int", "t_mm": 120,
     "axis": [[-181, 4890], [-181, 840]]}
  ],
  "labels": [
    {"room": "space_8", "type": "bedroom", "area_sqm": 11.1,
     "at": [-1551, 2859]}
  ]
  // 门 855mm 挂 1F:int:13 along 0.473 —— details 阶段生成（D44）

决策依据: 真实案例——客厅+阳台在南侧（采光面给起居），阳台贴客厅南边连续开敞。
反例: 厨房/卫生间占南侧起居位（真实案例厨房在北）→ 采光面浪费。

## pattern: 厨卫北侧集中（B_原始结构图实测，无 core 住宅）
命中痛点: P2-1 / P2-3
适用房间: kitchen / bathroom / toilet / dining
适用条件: {"wet_north_cluster": true, "has_core": false}
案例来源: B_原始结构图.dxf（无核心筒住宅）

设计要点: 厨卫+餐厅集中北分区（管线集中区）；卫生间邻厨房共享分界墙。

DSL 片段（同上节选——湿区房间组 = 多道分界墙围出邻接小间，门挂隔墙）:
  "walls": [
    {"key": "1F:int:8", "kind": "int", "t_mm": 120,
     "axis": [[-2931, 840], [-2931, 4090]]},
    {"key": "1F:int:13", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4090], [-2881, 4890]]},
    {"key": "1F:int:14", "kind": "int", "t_mm": 120,
     "axis": [[-2881, 4890], [-181, 4890]]}
  ],
  "labels": [
    {"room": "wet_a", "type": "bathroom", "area_sqm": 4.5, "at": [-1896, 3724]},
    {"room": "wet_b", "type": "kitchen", "area_sqm": 6.6, "at": [-1596, 4524]}
  ]
  // 门 855mm 挂 1F:int:13 along 0.47 —— details 阶段生成（D44）

决策依据: 无 core 住宅湿区北侧集中+邻接，管线共用（共墙直达管井）。
反例: 湿区散在南北对角 → 管线穿越全楼；编造"贴核心筒"（本案例无 core）→ 引用空目标。

## pattern: 卧室安静侧（B_原始结构图实测）
命中痛点: P2-2
适用房间: bedroom / master_bedroom / study
适用条件: {"bedroom_quiet_side": true}
案例来源: B_原始结构图.dxf

设计要点: 卧室/书房放东/北安静分区（远离南侧起居动线）；主卧套房（主卧+衣帽间同组）。

DSL 片段（节选 golden/residence/res_2s4u_std——安静分区房间组，共享墙+各挂门）:
  "walls": [
    {"key": "1F:int:8", "kind": "int", "t_mm": 120,
     "axis": [[-2931, 840], [-2931, 4090]]},
    {"key": "1F:int:9", "kind": "int", "t_mm": 120,
     "axis": [[-181, 840], [-2931, 840]]},
    {"key": "1F:int:22", "kind": "int", "t_mm": 120,
     "axis": [[-181, 4890], [-181, 840]]}
  ],
  "labels": [
    {"room": "bedroom_01", "type": "bedroom", "area_sqm": 11.1,
     "at": [-1551, 2859]},
    {"room": "master_01", "type": "master_bedroom", "area_sqm": 14.0,
     "at": [-596, 2924]}
  ]

决策依据: 真实案例——私密/安静空间在东侧，与南侧起居动线分离。
反例: 卧室贴南侧起居位 → 动线穿越私密区。
