## pattern: 无 core 住宅的湿区集中（B_原始结构图实测）
命中痛点: P2-1 / P2-3
适用房间: kitchen / bathroom / toilet / dining
适用条件: {"wet": true, "has_core": false}
案例来源: B_原始结构图.dxf（中国住宅，无核心筒）

设计要点: 无核心筒时厨卫+餐厅北侧集中（管线集中区），卫生间邻厨房共享分界墙。

DSL 片段（节选自 golden/residence/res_2s4u_std/rooms.std.json——湿区邻接组：
隔墙围出相邻小间，各间门挂隔墙，共墙管线直达）:
  "partitions": {"north_wet": "outline"},
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
  // 门 855mm 挂 1F:int:13 along 0.47 —— details 阶段按统一规律生成（D44）

决策依据: 无 core 住宅湿区北侧集中+邻接，管线共用；卫厨共享分界墙（管线直达）。
反例: 湿区散在南北对角 → 管线穿越全楼。

## pattern: 湿区邻接组团（共享分界墙，管线集中）
命中痛点: P2-3
适用房间: bathroom / kitchen / laundry
适用条件: {"wet_group": true}
案例来源: B_原始结构图.dxf

设计要点: 多个 wet 房沿连续墙轴排开（共享分界墙）——管线共墙，上下对应。

DSL 片段（同上节选——湿区组沿一道连续墙轴排，共墙 + 各挂门）:
决策依据: 真实案例卫厨相邻——wet 组团共享分界墙，管线集中。
反例: wet 房分散 → 管井穿全楼 → 上下不对位。

## pattern: 核心筒内厕所群（办公标准层，office_std_01 实测）
命中痛点: P2-1 / P2-4
适用房间: toilet_m / toilet_f / toilet_acc / pantry
适用条件: {"has_core": true, "type": "office"}
案例来源: golden/office/office_std_01

设计要点: 茶水间→男卫→女卫→无障碍卫（西→东一字排开），全部贴核心筒南侧，
不占外环采光面；四间共享隔墙；管井（JY/QD/PY 等）在筒内管线最短。

DSL 片段（节选自 golden/office/office_std_01/rooms.std.json——筒内 6.2㎡ 小间，
四墙围合 + 相邻小间共享分界墙）:
  "partitions": {"core_south": "corridor"},
  "walls": [
    {"key": "1F:int:20", "kind": "int", "t_mm": 120,
     "axis": [[14774, 20375], [14774, 22725]]},
    {"key": "1F:int:21", "kind": "int", "t_mm": 120,
     "axis": [[17424, 20375], [14774, 20375]]},
    {"key": "1F:int:22", "kind": "int", "t_mm": 120,
     "axis": [[14774, 22725], [17424, 22725]]},
    {"key": "1F:int:24", "kind": "int", "t_mm": 120,
     "axis": [[17424, 22725], [17424, 20375]]}
  ],
  "labels": [
    {"room": "toilet_m_01", "type": "toilet_m", "area_sqm": 6.2,
     "at": [16098, 21550]}
  ]

决策依据: 厕所群集中贴筒（管井在筒内管线最短）；茶水间与厕所同组（上下水共用）。
反例: 厕所拆散到办公区 → 管线穿越+占采光面（R-08）；首层照搬（lobby 实测无厕所）→ 功能冗余。
