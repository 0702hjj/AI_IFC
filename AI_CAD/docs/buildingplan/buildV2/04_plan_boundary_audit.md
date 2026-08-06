# 04 plan 职责边界审计：plan.json v2 草案的越界项

> 2026-08-06。前提：v2 架构（`README.md`）把**空间排布求解**划归 cad 阶段的
> 布局求解器（`01_layout_solver.md`)。据此回查
> `plan_format_research.md` §5 的 plan.json v2 草案——其中 plan 阶段的行为
> 是否越界。审计基准：架构文档 §4.1（plan=外部资料对接+关键参数框定+选项框
> 确认）与 §4.2（cad=平面布局取向/功能分区组织的交互核实）。

## 1. 逐字段审计

| 草案字段 | 内容 | 判定 | 理由 |
|---|---|---|---|
| `site` | 地块多边形/退线/北向 | ✅ 合法 | 外部约束，plan 本职 |
| `zones[].function` | 分区功能（retail/residence) | ✅ 合法 | 任务书核心，IfcZone 语义 |
| `zones[].floors` / `floor_height_mm` | 竖向分区+层高 | ✅ 合法 | stacking diagram,plan 经典产物 |
| `zones[].outline_mm` | 分区轮廓 | ✅ 合法 | 体块（massing）粒度，任务书/方案阶段产物；且 RPLAN 证据证明"只给轮廓"即可驱动下游 |
| `zones[].position` | 塔楼在裙房上的落位 | ✅ 合法 | 体块间关系，属 massing |
| `zones[].program` | 面积表（房间类型×数量×面积区间） | ✅ 合法 | Schedule of Accommodation,plan 的核心交付 |
| `standards` | 类型包引用+覆盖参数 | ✅ 合法 | 设计规范框定，§4.1 明示 |
| `vertical_relations` | 核心筒贯穿/屋面利用 | ✅ 合法 | 竖向体块关系，非平面排布 |
| `zones[].typology` | "步行街两侧商铺" | ⚠️ 边界 | 这是**布局范式选择**，按 §4.2 属 cad"绘制方向交互"的确认项；但 plan 可给候选集，拍板在 cad step2 |
| `zones[].layout.grid_hints` | 5×5 格位（核心筒居中/中庭居中） | ❌ **越界** | 粗位置=空间排布的直接表达，是求解器输入，属 cad step1 draft 的产物 |
| `zones[].layout.topology` | 邻接/连通/包含/朝向图 | ❌ **越界** | 这就是气泡图本身——v2 求解器的输入、HouseGAN++ 意义上"建筑师草图"，是 cad 的设计工作，不是 plan 的框定 |

## 2. 越界的本质

`layout.*` 不是"意图的描述"，而是**求解器的直接输入格式**——把它放进
plan.json 等于让 plan 阶段替 cad 做设计。v2 的职责链应该是：

```
plan(意图层):    轮廓 + 面积表 + 规范 + 竖向关系     ← “要什么”
cad(设计层):    气泡图(拓扑+格位) → 求解 → 坐标      ← “怎么排”
bim(交付层):    building.json + DXF → IFC            ← “盖出来”
```

plan 说了"要什么"（哪些房间、多大、什么功能分区），气泡图是"怎么排"的
开始，必须归 cad。

## 3. 修正方案：plan.json v2 瘦身 + cad 侧新增 draft 契约

**plan.json v2（瘦身版）** 删除 `layout` 整节，保留 §1 表中 ✅ 字段;
⚠️ 的 `typology` 降级为 `typology_candidates: [...]`(plan 给候选,cad step2
与用户拍板）。

意图级朝向怎么办？"卧室朝南"这类**设计要求**是合法的任务书内容——
但它应以**要求(requirement)**而非**图(graph)**的形态存在:

```jsonc
// plan.json v2 合法的做法:声明要求,不画关系
"requirements": [
  {"subject": "bedroom", "rule": "faces_south", "strength": "must"},
  {"subject": "bathroom", "rule": "near_core", "strength": "prefer"}
]
// 与 topology 的区别:requirement 是单房间+谓词,不含房间-房间边;
// 翻译成气泡图(和谁邻接、门开在哪)是 cad step1 的工作
```

**cad 侧新增 `cad_draft.json`**（即 step1 draft 的独立落盘，对齐架构文档
"cad 落盘=单一事实来源"):

```jsonc
{
  "version": 1,
  "source_plan": "plan.json 的 sha256",
  "zones": [{
    "id": "tower",
    "bubble_graph": {           // ← 原 plan.json 的 layout 节,搬家到这里
      "nodes": [{"id": "living", "type": "living", "area_sqm": 22, "cell": "center_south"}],
      "edges": [{"a": "living", "b": "kitchen", "via": "door"}],
      "hints": [{"node": "core", "cell": "center"}]
    },
    "typology": "central corridor",     // 从 plan 候选集中拍板
    "requirements_check": [             // plan requirements 的逐条落实说明
      {"rule": "bedroom faces_south", "status": "satisfied", "via": "S 面两间南卧"}
    ]
  }],
  "confirmed": false                    // cad step2 确认后置 true
}
```

## 4. 联动修订清单

| 文件 | 改动 |
|---|---|
| `plan_format_research.md` §5 草案 | 删 `layout` 节;`typology`→`typology_candidates`;加 `requirements` 节；标注"气泡图归 cad_draft.json" |
| `references/plan_contract.md`（尚未升 v2) | v2 化时按瘦身版写；`draft`/`confirmed` 状态机**移出** plan.json——那是 cad 的状态，plan.json 定稿即冻结 |
| `01_layout_solver.md` | 输入契约从"plan.json 的 layout 节"改为"cad_draft.json 的 bubble_graph" |
| `02_template_retrieval.md` | 模板检索结果的去向=cad_draft 初稿（原文已暗合，措辞同步） |
| `03_reconciliation.md` | R1-R8 对账的"plan 拓扑"改为"cad_draft 拓扑";requirements 的核对列入 step2 BY REVIEW |
| `steps/step-00/01/02`(aidxfv2) | step0 只校验 plan 瘦身字段；step1 产出 cad_draft.json（含气泡图）;step2 确认 bubble_graph + requirements_check |

## 5. 附带发现：状态机也要搬家

`plan_format_research.md` §5 的 `draft`/`confirmed` 字段同样是越界——
草案与确认是 **cad 的工作状态**，不是 plan 的内容。plan.json 的正确形态是：
**plan 阶段定稿后冻结，之后只读**;cad 的迭代状态全部写在 cad_draft.json
上。这与架构文档 §4.4"三处落盘各自是单一事实来源"完全一致。

## 6. 结论

- 越界 2 项：`layout.grid_hints`、`layout.topology`（连同桌上的 draft/confirmed
  状态机）→ 全部移入 cad 侧 cad_draft.json。
- 降级 1 项：`typology` → `typology_candidates`。
- 新增 1 节：`requirements`（单房间谓词式要求），承接合法的任务书级设计意图。
- plan 瘦身后的边界一句话：**plan 框定"要什么、在哪盖、什么规范";
  "谁挨着谁"从 plan.json 里消失，那是 cad 的第一笔。**
