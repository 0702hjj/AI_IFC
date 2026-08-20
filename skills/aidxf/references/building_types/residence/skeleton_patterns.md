# residence skeleton_patterns —— 骨架抽象模式（金例实测）

> 协议（skeleton.schema 唯一契约）：轴网机器派生（无 axis_grid 手填）、
> core 用 vertices 平铺顶点环（继承 plan core 真值）、corridor 用 ring_edges 四边拼合、
> 分区切割线锚定（from/to）+ blocks 认领。写前必读 references/orchestrator/skeleton.md。

## pattern: 并排多单元双核心筒四户（res_2s4u_std 实测）
命中痛点: P1-1 / P1-2 / P1-4
适用条件: {"standard_floor": true, "multi_unit": true, "multi_core": true}
案例来源: golden/residence/res_2s4u_std（一～三层共用标准层，522.86㎡/层）
分区概念（实测）:
  长板 44.3m×17.2m（aspect≈2.6），四户沿 x 排布：
  [户1][梯west][户2 ‖ 户3][梯east][户4]
  core×2   两个楼梯间核心筒（纯楼梯无电梯，2.4m×2.3m 各一）——
           左梯居中、右梯 **偏北错位**（真实特征，vertices 凸字形/偏移照抄 plan）
  corridor null（一梯两户：户门开向梯间前室，无公共走廊）
  units×4  每户面宽 9~10m，户边界 = 切割线（5 条：梯两侧 + 单元界，贯通南北）
DSL 片段（改参数即套用）:
  "core": [                                                            // 多核数组，各带 id
    {"id": "west", "anchor": [10900, 10950],                           // 锚点 = plan core_anchor_mm 锁死
     "vertices": [[9600, 9200], [12200, 9200], [12200, 12700], [9600, 12700]]},
    {"id": "east", "anchor": [32800, 13950],
     "vertices": [[31500, 12700], [34100, 12700], [34100, 15200], [31500, 15200]]}
  ],
  "corridor": null,
  "main_partitions": [                                                 // 户分界贯通南北（切割线锚定轮廓边）
    {"id": "cut:0", "role": "units|core 分界",
     "from": {"ref": "outline:edge:<南边>", "at": <梯西界/南边比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <梯西界/北边比>}},
    {"id": "cut:1", "role": "core|units 分界",
     "from": {"ref": "outline:edge:<南边>", "at": <梯东界/南边比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <梯东界/北边比>}},
    {"id": "cut:2", "role": "units|units 分界",
     "from": {"ref": "outline:edge:<南边>", "at": <单元界/南边比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <单元界/北边比>}}
  ]
  // 每户块由切割线围出：blocks 用 between 认领（{"id":"b0","role":"units",
  //   "between":["cut:0","cut:2"], "side":"W"}），side 消歧多候选段
决策依据: 真实案例——一梯两户无公共走廊（梯间前室服务两户，corridor=null）；
         双核心筒分居两单元（core 数组带 id）；户边界 = 切割线贯通南北（锚定轮廓边，
         at 比例表达梯/单元界位置——不手算坐标）。
反例: 多单元楼硬写单 core → 第二梯间无处安放；
      一梯两户写 corridor → 案例无走廊（户门开向前室）→ 面积浪费；
      切割线不贯通（内边界到外边界）→ 机器切不开大区 → 认领不到块
完整案例: golden/residence/res_2s4u_std/（skeleton.json + rooms.std.json）

## pattern: 商品住宅标准层分区（core + corridor + units）
命中痛点: P1-1 / P1-2 / P1-3
适用条件: {"standard_floor": true, "multi_unit": true}
分区概念（标准层骨架 = 三大区）:
  core    核心区域：楼梯 / 电梯 / 管井（竖向贯穿，plan 已定锚点/形状）
  corridor 走廊：连接各户门（板式/塔式——比办公短，户数少则短）
  units   各户（商品房）：每户一个区域，**户边界用切割线分隔**
block 词表: core / corridor / units / balcony（对齐 residence.cases.json ratio_standards）

DSL 片段（标准层骨架，改参数即套用）:
  "core": {
    "anchor": [<plan core 锚点>],
    "vertices": [[<x0>,<y0>],[<x1>,<y0>],[<x1>,<y1>],[<x0>,<y1>]]  // 继承 plan core 真值（凸字形就凸字形）
  },
  "corridor": {                                // 短廊外缘 = ring_edges 四边拼合（带形走廊也是闭合外缘）
    "form": "path",
    "width_mm": 1500,                          // 住宅短廊 1400~1600（办公 2400+）
    "path": {"edges": {
      "west":  [[<x0>, <y0>], [<x0>, <y1>]],   // 角点共享：west 末 = north 首 = 西北角
      "north": [[<x0>, <y1>], [<x1>, <y1>]],
      "east":  [[<x1>, <y1>], [<x1>, <y0>]],
      "south": [[<x1>, <y0>], [<x0>, <y0>]]}}
  },
  "main_partitions": [                         // ★户边界用切割线分隔（锚定，不手算坐标）
    {"id": "cut:0", "role": "units|units 分界",
     "from": {"ref": "outline:edge:<南边>", "at": <户界比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <户界比>}},
    {"id": "cut:1", "role": "units|corridor 分界",
     "from": {"ref": "corridor:outer", "edge": "S", "at": <户界比>},
     "to":   {"ref": "outline:edge:<南边>", "at": <户界比>}}
  ],
  "blocks": [                                  // 认领切割段为户块
    {"id": "b_w", "role": "units", "between": ["cut:0", "cut:1"], "side": "W"}
  ]
决策依据: 标准层骨架 = 核心筒（竖向贯穿）+ 短走廊（连户门）+ 各户（切割线分隔）——
         户边界由 main_partitions 显式划出（role=units），不是靠房间填充隐式生成。
反例: 把户边界留到 rooms 阶段"房间边界派生"→ 户与户之间缺显式划分线；
      corridor 画成办公长廊（住宅短廊 1.4-1.6m，办公 2.4m+）→ 得房率浪费

## pattern: 无 core 住宅（单户/独立住宅骨架）
命中痛点: P1-4
适用条件: {"floors_count": 1, "has_core": false, "single_unit": true}
分区概念: 无核心筒 → 无 core/corridor 区；分区 = 户内三带（room_patterns 学）：
  南带采光起居（客厅+阳台）→ 中带安静（卧室/书房）→ 北带管线（厨卫+餐厅）
DSL 片段:
  "core": null,                     // 无核心筒
  "corridor": null,                 // 无独立走廊（案例实测：房间直接相邻）
  "main_partitions": [              // 户内带界也用切割线（锚定轮廓边）
    {"id": "cut:0", "role": "living|bedroom 分界",
     "from": {"ref": "outline:edge:<东边>", "at": <带界比>},
     "to":   {"ref": "outline:edge:<西边>", "at": <带界比>}}
  ]
决策依据: 单户/独立住宅无 core/corridor（floorplan_structure 实测）；
         户内分区归 room_patterns（三带式：南起居/中安静/北管线）。
反例: 强行造 core → adjacent_to core 房间引用空目标 SchemaError；
      硬画走廊 → 案例无走廊（房间直接相邻）→ 浪费面积
