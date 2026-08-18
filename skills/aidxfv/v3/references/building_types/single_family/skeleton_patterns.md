# single_family skeleton_patterns —— 骨架抽象模式（金例实测）

> 协议：D42 硬化——无 axis_grid 手填、core 用 vertices、切割线锚定 + blocks 认领；
> rooms 层 D41——walls + labels（D44：openings 归 details 统一规律，rooms 不声明）。

## pattern: 美式独栋两区分区（主屋 + 车库）
命中痛点: P1-1 / P1-2
适用条件: {"single_family": true, "has_garage": true}
案例来源: golden/single_family/floorplan_structure（Bishop-Overland-08，2-car garage）
分区概念（实测）:
  独栋 = **主屋 + 车库** 两个大块（无 core / 无公共走廊）：
  主屋分四区——
    公共起居带（东）:       DINING + KITCHEN（开放布局无隔墙，GREAT ROOM 居中偏东）
    私密带（西）:           MASTER + HALL + W.I.C.（主卧套房远离入口）
    入口（西）:             ENTRY + COVERED PORCH（西侧门廊入口）
    车库（南）:             GARAGE + WH（2-car 独立区，车库门 16'=4877mm）
  户外延伸（不算房间）:     DECK（东 2.5m×4.4m）+ COVERED PORCH（西 2.2m×1.3m）
DSL 片段（骨架声明）:
  "core": null,                       // 独栋无核心筒（词表差异，非 bug）
  "corridor": null,                   // 无公共走廊（HALL 是室内短廊非 corridor 区）
  "main_partitions": [
    {"id": "cut:0", "role": "garage|living 分界",       // 车库/主屋共享墙 → 切割线锚定
     "from": {"ref": "outline:edge:<车库东界边>", "at": <共享墙位置比>},
     "to":   {"ref": "outline:edge:<对面边>", "at": <位置比>}},
    {"id": "cut:1", "role": "living|bedroom 分界",      // 主屋横墙
     "from": {"ref": "outline:edge:<北边>", "at": <横墙比>},
     "to":   {"ref": "outline:edge:<南边>", "at": <横墙比>}}
  ],
  "blocks": [
    {"id": "b_garage", "role": "garage", "between": ["cut:0"], "side": "S"},
    {"id": "b_house", "role": "units", "between": ["cut:0"], "side": "N"}
  ],
  "special_openings": [               // 车库门 16'（特征开口）
    {"at": [<车库门中线点>], "reason": "garage_door_4877mm"}
  ]
决策依据: 真实案例——独栋 = 主屋+车库；车库独立区带 16' 门；主屋东侧公共起居、
         西侧私密、西入口门廊（管线短）。
反例: 套商品房 core+corridor 词表 → 独栋无 core SchemaError；
      车库当普通房间（无 special_openings/独立块）→ 类型特征丢失；
      私密带放南侧 → 采光面被卧室独占，起居靠北无光（R-08）

## pattern: 无车库独栋（单块主屋）
命中痛点: P1-2
适用条件: {"single_family": true, "has_garage": false}
分区概念: 无车库 → 单块主屋，四区照旧（公共起居东 / 私密西 / 入口西 / 无车库），
  户外 DECK/PORCH 延伸（不算房间）。
DSL 片段: 同主屋四区，无 cut:0（车库/主屋界）与 garage 块
决策依据: 车库是可选特征区（车库可后加建/无车家庭），主屋分区不变。
反例: 无车库还写 garage block → 无依据；户外平台当房间 → 面积虚增

## pattern: 开放起居带（GREAT ROOM 无隔墙）
命中痛点: P2-4 / P2-5
适用条件: {"open_plan": true}
案例来源: golden/single_family/floorplan_structure（GREAT ROOM 居中偏东，
          DINING+KITCHEN 东侧开放）
DSL 片段: 起居/餐厅/厨房三房合成一个开放带，**不画内隔墙**（D41：声明墙，不声明房间）
  "walls": [                          // 只画带界墙，带内不画起居/餐/厨隔墙
    {"key": "1F:int:0", "kind": "int", "t_mm": 120,
     "axis": [[<带界起点>], [<带界终点>]]}
  ],
  "labels": [                         // 三房标签落同一墙围区域（分区内）
    {"room": "great_01", "type": "living", "area_sqm": <30~50>, "at": [<东区点>]},
    {"room": "dining_01", "type": "dining", "area_sqm": <>, "at": [<东区点>]},
    {"room": "kitchen_01", "type": "kitchen", "area_sqm": <>, "at": [<东区点>]}
  ]
决策依据: 真实案例——美式独栋起居常为开放布局（GREAT ROOM 无隔墙大空间）。
反例: 起居/餐/厨硬画隔墙 → 破坏开放布局；采光面只给起居不给餐厨 → 暗厨（R-08）

## pattern: 主卧套房（MASTER + W.I.C.）
命中痛点: P2-2 / P2-4
适用条件: {"master_suite": true}
案例来源: golden/single_family/floorplan_structure（MASTER 西侧 + W.I.C. 衣帽间 + HALL 连通）
DSL 片段: 主卧带衣帽间，独立于其他卧室——墙围出套房，标签落区
  "walls": [
    {"key": "1F:int:0", "kind": "int", "t_mm": 120,          // master/wic 分界墙
     "axis": [[<master/wic 分界两端>]]},
    {"key": "1F:ext:0", "kind": "ext", "t_mm": 200,          // 套房外墙（贴轮廓）
     "axis": [[<西侧外墙折线>]]}
  ],
  "labels": [
    {"room": "master_01", "type": "bedroom", "area_sqm": <>, "at": [<卧室区点>]},
    {"room": "wic_01", "type": "closet", "area_sqm": <>, "at": [<衣帽间区点>]}
  ]
  // 主卧↔衣帽间门：details 阶段按统一规律挂 1F:int:0（D44）
决策依据: 真实案例——主卧套房（卧室+衣帽间）是美式独栋标配，靠西私密远离入口。
反例: 主卧不带衣帽间（W.I.C. 是独立房）→ 收纳缺失；主卧放东 → 与公共起居动线交叉
