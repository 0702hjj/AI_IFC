## pattern: 无独立走廊的住宅（B_原始结构图/floorplan 实测）
命中痛点: P2-1 / P2-4
适用房间: corridor / hall（或省略——住宅可无独立走廊）
适用条件: {"no_corridor": true}
案例来源: B_原始结构图.dxf + floorplan_结构.dxf

设计要点: 小型住宅不设独立走廊房间——房间直接相邻连通（门对门/门对厅）。
走廊是骨架分层外推的产物：骨架没有 corridor 就不声明（不得编造去引用）。

DSL 片段（节选自 golden/single_family/floorplan_structure/rooms.F1.json——
12.8㎡ 房间，阶梯状外墙 + 内隔墙围合，无走廊区域）:
  "partitions": {"main": "outline"},
  "walls": [
    {"key": "1F:int:55", "kind": "int", "t_mm": 120,
     "axis": [[2475, 3617], [2475, 6717]]},
    {"key": "1F:int:56", "kind": "int", "t_mm": 120,
     "axis": [[5825, 3617], [2475, 3617]]},
    {"key": "1F:int:57", "kind": "int", "t_mm": 120,
     "axis": [[2475, 6717], [2525, 6717]]},
    {"key": "1F:int:58", "kind": "int", "t_mm": 120,
     "axis": [[2525, 6717], [2525, 7417]]},
    {"key": "1F:int:76", "kind": "int", "t_mm": 120,
     "axis": [[5825, 7417], [5825, 6367]]},
    {"key": "1F:int:77", "kind": "int", "t_mm": 120,
     "axis": [[5825, 6367], [5875, 6367]]}
  ],
  "labels": [
    {"room": "space_5", "type": "unlabeled", "area_sqm": 13,
     "at": [4175, 5367]}
  ]

决策依据: 真实案例——小型住宅房间直接相邻（共享墙+门），无独立走廊。
反例: 编造走廊（骨架无 corridor）→ 引用空目标；走廊占面积 → 房间塞不下。

## pattern: 房间直接相邻连通（无走廊动线）
命中痛点: P2-4
适用房间: 所有（无走廊住宅）
适用条件: {"direct_adjacency": true}
案例来源: B_原始结构图.dxf

设计要点: 房间间共享墙 + 门（每房间 1 门连通）；私密房（卧室）门与起居门错开（不对门）。

DSL 片段: 房间标签沿共享墙两侧落区；门在 details 阶段挂共享墙 key + along 错位（D44）。
决策依据: 真实案例——房间直接相邻，门挂共享墙；卧室门与起居门错开。
反例: 房间孤立（无共享墙）→ R-07 飞地；对门穿堂 → 隐私破坏。

## pattern: 核心筒环廊连通（办公标准层，office_std_01 实测）
命中痛点: P2-1 / P2-4
适用房间: corridor（环形绕 core）+ 周边 office
适用条件: {"has_core": true, "corridor_form": "path"}  # 环廊 = ring_edges 分段外缘 − core 差集（D42）
案例来源: golden/office/office_std_01（10 户办公环核心筒四边）

设计要点: 环廊是骨架分层外推产物（corridor 外缘−核差集）——rooms 不声明走廊区域，
办公房间门全朝环廊开（门挂贴廊侧墙）。

DSL 片段（节选自 golden/office/office_std_01/rooms.std.json——环廊侧办公小间，
四墙围合，邻间共享隔墙）:
  "partitions": {"office_n": "outline", "ring": "corridor"},  // office_std_01 迁移后引用
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
    {"room": "office_01", "type": "office", "area_sqm": 6.2,
     "at": [16098, 21550]}
  ]

决策依据: 环廊绕核心筒，办公四边全采光、门全朝环廊；电梯厅直接接环廊（垂直→水平交通零距离）。
反例: 办公门朝外墙开 → 环廊成摆设+疏散失效；环廊断头 → 环流不成环（R-07 连通断裂）。
