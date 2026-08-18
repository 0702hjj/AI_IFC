# office skeleton_patterns —— 骨架抽象模式（金例实测）

> 协议：D42 硬化——无 axis_grid 手填（轴网机器派生）、core 用 vertices 平铺、
> corridor 用 ring_edges 四边拼合（无 form=ring）、分户切割线锚定 + blocks 认领。

## pattern: 核心筒居中环廊 + open_office 分户（办公标准层）
命中痛点: P1-1 / P1-3 / P1-4
适用条件: {"aspect_ratio_max": 1.3, "deep_zone_ratio_max": 0.35}（近方形/浅板——geom 派生字段可判）
案例来源: golden/office/office_std_01（47.5×46.0m 近方形**非标准矩形**——西翼凹槽带/东翼凸出/北排分户凹槽）

骨架四件套（block 词表对齐 office.cases.json：core/corridor/open_office）:
  ① core      核心筒居中 16.7×17.1m（占 15.6%）：vertices 平铺顶点环（继承 plan core 真值）
              内含电梯厅/服务梯/前室×2/管井群/机房/厕所群
  ② corridor  环廊外缘 = core bbox 外扩 2400 的闭合环（ring_edges 四边拼合）——
              机器差集外缘 − core = 环带
  ③ open_office 分区  环廊与外轮廓之间即办公区（北排/南排/西翼/东翼四带）
  ④ main_partitions   **分户初级切分**（不同公司办公房区分——骨架级决策）：
              北排/南排分户墙 x14000/23000/32060（开间 9~12m）
              西翼分户 y18500/27500；东翼分户 y27500
              → 10 户落位实测全对（01:0~14 / 02:14~23 / 03:23~32 / 04:32~44.4 北排，南排镜像，东西翼各 1）

DSL 片段（改参数即套用）:
  "core": {"anchor": [23698, 22950],                       // 锚点 = plan core_anchor_mm 锁死
           "vertices": [[15400, 14400], [31997, 14400], [31997, 31500], [15400, 31500]]},
  "corridor": {"form": "path", "width_mm": 2400,
    "path": {"edges": {                                   // 外缘 = core bbox 外扩 2.4m
      "west":  [[13000, 12000], [13000, 33900]],
      "north": [[13000, 33900], [34397, 33900]],
      "east":  [[34397, 33900], [34397, 12000]],
      "south": [[34397, 12000], [13000, 12000]]}}},
  "main_partitions": [                                    // 分户切割线：锚定环廊外缘 → 轮廓边
    {"id": "cut:0", "role": "open_office|open_office 分界（北排）",
     "from": {"ref": "corridor:outer", "edge": "N", "at": <分户墙/北外缘比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <分户墙/北边比>}},
    {"id": "cut:1", "role": "open_office|open_office 分界（南排）",
     "from": {"ref": "corridor:outer", "edge": "S", "at": <分户墙/南外缘比>},
     "to":   {"ref": "outline:edge:<南边>", "at": <分户墙/南边比>}},
    {"id": "cut:2", "role": "open_office|open_office 分界（西翼）",
     "from": {"ref": "corridor:outer", "edge": "W", "at": <分户墙/西外缘比>},
     "to":   {"ref": "outline:edge:<西边>", "at": <分户墙/西边比>}}
  ],
  "blocks": [                                             // 户块认领（between 切割线 + side 消歧）
    {"id": "b_n1", "role": "open_office", "between": ["cut:0"], "side": "W"},
    {"id": "b_n2", "role": "open_office", "between": ["cut:0"], "side": "E"}
  ]
决策依据:
- 分户切割线锚定**真实轮廓边**（非标准矩形）：凹槽/凸出处轮廓边多段——at 比例按实际边算，
  不假设矩形外包（轮廓顶点照抄 plan outline_mm）；
- 分户是**骨架级**（main_partitions）不是 rooms 级——不同公司办公房的产权/租区边界在骨架冻结时锁定，
  rooms 层只在户内做设计（区域内全量自由，跨户墙不动）；
- 核心筒居中 → 四带办公全采光（R-08）；服务功能全收筒内（R-09 暗区零浪费）。
反例: 分户墙不上骨架（留 rooms 层自由切）→ 跨户墙被 worker 改 → 产权边界丢失；
      切割线不贯通（环廊外缘 ↔ 轮廓边缺一端锚定）→ 机器切不开 → 块认领失败；
      核心筒贴边 → 环廊退化单侧长廊（R-09）

## pattern: 首层大堂变体（核心筒同位 + 公共功能让位 + OP 商铺分户）
命中痛点: P1-1 / P1-5
适用条件: {"floor": "lobby"}（首层/大堂层）
案例来源: golden/office/office_lobby_01（49.0×48.7m 非标准矩形）
与标准层的同与异（首层特殊性——实测）:
  同: core vertices/anchor 同位标准层（楼电梯管井竖向贯穿，R-06 跨层对齐）；环廊 ring_edges 同
  异（首层特有）:
    ① 西翼整翼让位 **办公大堂+入口+接待**（切割线划 lobby|open_office 分界）
    ② **消防控制中心** @南东（规范首层必设，贴外墙独立疏散）
    ③ **无厕所**（首层不设，大堂配套解决）
    ④ 地下车库入口+疏散通道×2（首层水平疏散）
    ⑤ **OP01~12 商铺**集中西翼中段三排（开间 ~3m）——分户更细：
       主分户 x21400 + 排分隔 y27000/30700（骨架给主分户，细分户 rooms 层）
DSL 片段:
  "core": {"anchor": [25210, 24150],                    // 同标准层锚点（R-06 跨层对齐）
           "vertices": [[...]]},                        // 同标准层 vertices
  "corridor": {"form": "path", "width_mm": 2400,        // 同标准层 ring_edges
    "path": {"edges": {...}}},
  "main_partitions": [
    {"id": "cut:0", "role": "open_office|lobby 分界（大堂东墙）",
     "from": {"ref": "outline:edge:<南边>", "at": <大堂东墙/南边比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <大堂东墙/北边比>}},
    {"id": "cut:1", "role": "open_office|open_office 分界（OP 主分户）",
     "from": {"ref": "outline:edge:<南边>", "at": <主分户/南边比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <主分户/北边比>}},
    {"id": "cut:2", "role": "open_office|open_office 分界（OP 排间）",
     "from": {"ref": "outline:edge:<东边>", "at": <排分隔/东边比>},
     "to":   {"ref": "outline:edge:<西边>", "at": <排分隔/西边比>}}
  ],
  "blocks": [
    {"id": "b_lobby", "role": "lobby", "between": ["cut:0"], "side": "W"},
    {"id": "b_op", "role": "retail", "between": ["cut:0", "cut:1"], "side": "W"}
  ]
决策依据: 核心筒竖向贯穿不可动（R-06）；首层公共性最强 → 大堂/消控/疏散占外环；
         OP 商铺分户细（~3m 开间），骨架只锁主分户与排分隔，商铺内组合留给 rooms 层。
反例: 首层照搬标准层分户 → 无大堂/无消控 → 功能缺失规范不过；
      OP 每间商铺都上骨架分户 → 骨架过碎（商铺合并灵活性丢失）
