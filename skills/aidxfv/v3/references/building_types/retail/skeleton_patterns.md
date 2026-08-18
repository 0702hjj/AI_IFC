# retail skeleton_patterns —— 骨架抽象模式（金例实测）

> 协议：D42 硬化——无 axis_grid 手填、corridor 用 ring_edges 四边拼合（无 form=ring）。

## pattern: 中庭环绕（商业）
命中痛点: P1-1 / P1-3
适用条件: {"has_atrium_hole": true}
决策要点:
- 轴网机器派生（中庭周边 4.5~6m 开间是**设计结果**，不手填 axis_grid）
- corridor: 外缘 = 中庭孔洞外扩的闭合环（ring_edges 四边拼合，宽度 2400~3000）
- main_partitions: 主力店 at_end，小铺沿环廊（切割线锚定 corridor:outer → outline 边）
DSL 片段:
  "corridor": {
    "form": "path",
    "width_mm": 3000,
    "path": {"edges": {                       // 外缘 = 中庭孔洞 bbox 外扩 3m 的矩形环
      "west":  [[<x0>, <y0>], [<x0>, <y1>]],  // 角点共享：west 末 = north 首
      "north": [[<x0>, <y1>], [<x1>, <y1>]],
      "east":  [[<x1>, <y1>], [<x1>, <y0>]],
      "south": [[<x1>, <y0>], [<x0>, <y0>]]}}
  },
  "main_partitions": [                       // 小铺分界：切割线锚定环廊外缘 → 轮廓边
    {"id": "cut:0", "role": "shop|shop 分界",
     "from": {"ref": "corridor:outer", "edge": "N", "at": <铺界比>},
     "to":   {"ref": "outline:edge:<北边>", "at": <铺界比>}}
  ],
  "blocks": [
    {"id": "b_anchor", "role": "anchor_store", "between": ["cut:0"], "side": "E"},
    {"id": "b_shops", "role": "retail", "between": ["cut:0"], "side": "W"}
  ]
决策依据: 中庭是商业核心动线（一眼看全层），环廊服务所有店铺；环带 = corridor 外缘
         − 中庭孔洞（机器差集自动），rooms 阶段在环带两侧画铺墙。
反例: 无孔轮廓选中庭环绕 → typology 与几何脱节（Q1 失败）；
      手填 axis_grid → 轴网与几何漂移（D42 后轴网派生，手填被 schema 拒绝）
