# 02 模板检索：Graph2Plan 式起步，不从空白开始

> Graph2Plan 的核心交互：用户给轮廓+约束 → 从 80K 图模板库**检索最像的布局图**
> → 在模板上改（调房间数/邻接/位置）→ 生成。v2 把这一步搬到我们的金样资产上：
> **step1 草案不从空白推理，先检索最接近的历史布局图，改造它。**

## 1. 为什么可行（我们的独特优势）

Graph2Plan 要花一篇文章的篇幅从平面图**提取** layout graph（门检测、距离阈值
补邻接、5×5 格位、面积比）。**我们的金样 DXF 天生带语义**，解析是确定性的：

- 房间节点：`A-ANNO-TEXT` 层的 room_label（名字+面积，archdxf annotate 写入）
- 房间多边形：由墙段围合反推，或生成时顺手落盘 `layout.json`（零成本，
  见 §4)
- 门边：`A-DOOR` 层 swing 实体所在墙段两侧的房间 → door 边
- 窗/front_door:`A-GLAZ` 在外墙上的开洞、外墙门 → front_door 边
- 粗位置：房间质心 → 5×5 格位（Graph2Plan 同款）
- 外轮廓：外墙外缘

**结论：每一个 v1 金样（residence_1br、mall_l1、scaffold 默认案）都能无损
反编译回气泡图**——模板库不用外购数据集，从自己积累的金样长出来。

## 2. 模板库格式（layout graph JSON）

```jsonc
{
  "id": "residence_1br",
  "source_dxf": "results/golden/residence_1br.dxf",
  "function": "residence",
  "outline_mm": [[0,0],[8000,0],[8000,10000],[0,10000]],
  "nodes": [
    {"id": "living", "type": "living", "area_sqm": 21.6,
     "cell": "center_south",            // 5×5 格位
     "area_ratio": 0.27}                // Graph2Plan 节点三元组:类型/格位/面积比
  ],
  "edges": [
    {"a": "living", "b": "kitchen", "via": "door"},
    {"a": "living", "b": "outside", "via": "front_door"},
    {"a": "bedroom", "b": "living", "via": "door"}
  ],
  "orientation": [{"node": "bedroom", "faces": "south"}]
}
```

节点三元组直接照 Graph2Plan（类型/格位/面积比），边类型照 HouseGAN++
(door/front_door)——与 plan.json v2 的 `layout.topology` 同一词表，
检索结果就是可直接编辑的 draft 素材。

## 3. 相似度度量（检索键）

Graph2Plan 的检索键：房间数量约束 + 位置/邻接约束过滤 + **源轮廓与目标轮廓
的相似度排序**。我们的版本（全部确定性计算）:

| 键 | 计算 | 权重 |
|---|---|---|
| 功能类型 | zone.function 相等过滤 | 硬过滤 |
| 房间类型多重集 | 类型计数向量的 L1 距离 | 中 |
| 轮廓形状 | 长宽比 + 直角多边形转角序列相似度（turning function) | 高 |
| 面积规模 | 总面积比值 | 中 |
| 拓扑距离 | 图编辑距离（节点类型替换代价 1，边增删 1) | 高（有拓扑约束时） |

排序输出 top-3，模型 BY REVIEW 选一个改造——**选择权在模型，计算在机器**。

## 4. 库的增长机制

- 每次 v2 交付（step4）顺手把该案的 layout graph JSON 落盘进库——
  **每做一个项目，模板库自动大一条**，这是飞轮。
- 生成侧零成本方案：求解器本来就产出房间多边形+门位，序列化成 §2 格式
  即可；v1 老金样用反编译脚本补（一次性）。

## 5. 与求解器的衔接

检索不是替代求解器，而是给它**更好的起点**:

1. 模板的气泡图 → 作为 plan draft 的初稿（模型改房间数/面积/边）
2. 模板的格位分布 → 作为 grid_hints 初值
3. 轮廓高度相似时（如同地块改方案），模板的栅格分配可作 CP-SAT 的
   warm-start hint，加速且结果更稳

## 6. 待定项

1. 模板库落盘位置：`skills/aidxfv2/references/templates/*.json`（随 skill
   分发）还是 `results/templates/`（项目侧积累）?——倾向两者：skill 内置
   3 个种子模板（三个金样），项目侧自动增长。
2. 图编辑距离自己实现（小图，穷举可承受）还是简化成边集合编辑代价？——
   倾向简化版，模板 <50 节点时精确 GED 也没必要。
3. v1 金样反编译脚本放 `scripts/` 一次性工具，还是 layout 包的常驻能力
   （`layout.from_dxf`)?——倾向常驻，对账机制（03）也需要"DXF→图"。
