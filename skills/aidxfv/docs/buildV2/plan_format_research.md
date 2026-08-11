# plan 落盘格式调研：商住楼场景驱动的 plan.json v2 设计

> 2026-08-06。动机：现 `references/plan_contract.md` v1 的 plan.json 假设单一建筑类型、
> 统一轮廓，无法表达商住楼这类**竖向功能分区 + 分区轮廓 + 分区内部面积表与排布**的
> 真实 plan 产物。本文调查"plan 阶段到底要承载什么信息、业界怎么表示"，给出 v2 结构
> 建议，供随后修订 plan_contract.md 使用。
>
> 2026-08-06 增补：已下载并精读 5 篇一手论文（PDF 在 `AI_CAD/research/`),§3.1 为
> 原文提炼。
>
> 2026-08-06 v2.1：**按职责边界审计（`04_plan_boundary_audit.md`）修订**——
> 空间排布求解归 cad 后，`layout.*`（气泡图/格位）与 draft/confirmed 状态机从
> plan.json 移出至 cad 侧 `cad_draft.json`;§5 已重写为瘦身版 plan.json v2 +
> cad_draft.json 契约；§3 的排布词表（连通/方位/格位/包含）保留，但其归属是
> **cad_draft 的词表**，不再是 plan 字段。

## 1. 需求拆解：商住楼 plan 实际要说什么

以一栋"1-3F 商场 + 4-18F 住宅"的商住楼为例，plan 阶段需要框定的信息层：

| 信息层 | 例子 | 谁消费 |
|---|---|---|
| 竖向功能分区 | 1-3F=商场（裙房），4-18F=住宅（塔楼），屋顶=设备层 | cad 拆层绘制的总纲 |
| 分区轮廓 | 裙房轮廓 60m×40m 矩形；塔楼轮廓 24m×18m,落在裙房北部居中 | cad 每层外墙边界 |
| 分区面积表 | 商场：主力店 2000㎡×1、商铺 80-120㎡×n、中庭；住宅：两房 75㎡×2/层、三房 95㎡×2/层 | cad 房间划分 |
| 空间排布意图 | 住宅卫生间靠核心筒管井；商铺沿步行街两侧；卧室朝南 | **cad 气泡图**（v2.1 起 plan 只承载 requirements 谓词形态，不画房间关系） |
| 设计标准 | 走廊净宽、日照/防火分区、无障碍；引用类型包 + 显式覆盖 | cad T0/类型包之外的硬约束 |
| 竖向关系 | 住宅核心筒必须贯穿裙房落位；裙房屋面=住宅架空花园 | bim 阶段 + cad 楼梯/电梯占位 |

v1 的缺口:`building_type` 单值、`site` 只有地块、无分区概念、program 是平铺
房间列表、完全没有"轮廓"与"排布"两个维度。

## 2. 建筑设计工作流里的对应物

plan 落盘本质是**设计任务书(design brief)+ 方案构思**的机器可读化。事务所流程中
对应的成熟文档：

1. **面积表(Schedule of Accommodation / area program)**:房间名×数量×目标面积×
   功能分区归属。这是所有生成式工具的输入核心。
2. **竖向功能分区图(stacking diagram)**:商住楼的标准表达——竖条图上标注每段
   楼层的功能、层高、轮廓关系(裙房 podium / 塔楼 tower)。这正是"哪几层商场、
   哪几层住宅"的业界表达。
3. **气泡图(bubble diagram)**:节点=功能空间(面积近似正比),边=必须相邻/连通。
   表达"内部空间怎么排布"的前几何阶段,不含坐标。
4. **体块/块面图(massing / block plan)**:各功能体块的轮廓与相对位置,平面到
   "分区轮廓"粒度,不含内墙。

关键观察:**排布意图在业界本来就是图(邻接关系)而非坐标**。plan 阶段给坐标是
过度框定,cad 阶段需要布局自由度。v2.1 审计后的最终归属:气泡图(邻接图)
是 **cad 的设计产物**(cad_draft.json);plan 最多携带单房间谓词式的
requirements(如"卧室朝南"),不含房间-房间边——见 `04_plan_boundary_audit.md`。

## 3. 已有机器可读格式调查

### 3.1 学术论文精读（一手来源，PDF 在 `research/`)

**① RPLAN —— Wu et al., "Data-driven Interior Plan Generation for Residential
Buildings", SIGGRAPH Asia 2019**(`research/rplan_wu2019.pdf`，项目页
staff.ustc.edu.cn/~fuxm/projects/DeepLayout/)

- 数据集：真实亚洲住宅市场收集 120K+ 户型，过滤后 80K+；每张图是**矢量表示，
  归一化在 18m×18m 方形区域内**，含几何+语义；为学习转 256×256 四通道图
  (inside mask / boundary / 房间与墙语义整数标号 / 同类房间实例区分）。
- 房间类型过滤后 **13 类**;过滤规则本身是 plan 级约束的实例：总面积 60-120㎡、
  房间数 3-9、**必须有客厅**、客厅面积占比 0.25-0.55、房间均面积 10-20㎡。
- 生成管线：输入只有**建筑外轮廓**；两阶段先定位房间再定墙。
  **"living room first"策略的观察：客厅通常位于平面中心且连接绝大多数房间**
  ——连通枢纽是住宅平面的一阶特征。
- 对我们的意义：①轮廓作为唯一几何输入即可驱动整套平面，证明 plan 只需给到
  轮廓粒度；②过滤规则（面积区间/房间数区间/必备房间/占比）全部是 plan.json
  program 的自然字段；③"枢纽房间"概念可用于 step1 草案的布局种子。

**② Graph2Plan —— Hu et al., ACM TOG 2020, arXiv:2004.13204**
(`research/2004.13204.pdf`)

- **输入 = 建筑外轮廓 + layout graph（布局图）**，用户约束三类：房间数量、
  房间位置、房间邻接；另支持从 RPLAN 80K+ 图模板检索起步再编辑。
- layout graph 节点编码三元组：**房间类型（13 类，同 RPLAN)+ 位置（外轮廓
  包围盒划 5×5 网格，房间中心所在格）+ 大小（房间面积/建筑面积比值）**。
- 边编码**10 种有向空间关系**:left of / right of / above / below /
  left-above / right-above / left-below / right-below / inside / outside。
- 邻接对判定：先取门两侧的房间，再补距离小于阈值的对。
- 对我们的意义：**"5×5 网格格位"是不给坐标又能表达位置的成熟方案**——plan
  的"排布"可以用"九宫格式方位格 + 邻接边"表达，把精确坐标留给 cad;
  inside/outside 两种关系正好表达"中庭内嵌""外挂阳台"这类包含/外挑。

**③ HouseGAN++ —— Nauata et al., CVPR 2021, arXiv:2103.02574**
(`research/2103.02574.pdf`)

- **输入 = 气泡图**：节点=房间类型（10 类，含伪节点 "outside")；关键演进——
  **边从"空间相邻"改为"功能连接"，只有两种：interior door（房间-房间）/
  front door（房间-室外）**，作者明确说这是照真实建筑师草图建模的。
- 数据：RPLAN 解析出 60k 户型+对应气泡图；输出分割掩码再矢量化（轴对齐闭合
  多边形、相邻房间共享墙线段）。
- 对我们的意义：**连通关系的最佳词表可能就是"有内门 / 有前门（通室外）"**，
  而非抽象的 must/prefer/avoid——门本身就是 DXF 阶段要画的东西，plan 说
  "A 与 B 之间有门"比"A 与 B 必须相邻"更可直接执行、可校验（cad 阶段
  门表 vs plan 连通表对账）。

**④ HouseExpo —— Li et al. 2019, arXiv:1903.09845**(`research/1903.09845.pdf`)

- 35,126 户型 / 252,550 房间（SUNCG 来源）；**JSON 存储：结构=以户型质心为
  原点、米为单位的线段集合**，房间类别标签继承 SUNCG 枚举。
- 对我们的意义：轮廓/墙体的 JSON 表达用**线段集 + 质心原点约定**即可，
  无需复杂 schema；类目枚举要有权威来源（我们的类型包 T2 词汇表即对应物）。

**⑤ Tell2Design —— arXiv:2311.15941**(`research/2311.15941.pdf`)

- 语言指令→户型的数据集（基于 RPLAN 80,788 张，合并为 8 类房间）；把设计
  指令分解为三要素，这个分解可直接借用为 plan.json 的字段划分：
  - **Semantics**：房间类型与功能；
  - **Geometry**：房间的**朝向（north / northeast 等 8 向）、面积、长宽比**;
  - **Topology**：房间间关系，分三类——**relative location（相对方位）/
    connectivity（连通）/ inclusion（包含）**。
- 位置说法实例："north side" / "southeastern corner"；关系说法实例：
  "next to" / "between" / "opposite"。
- 对我们的意义：排布约束的完整词表 = **方位（8 向 + side/corner 修饰）×
  拓扑三类（方位/连通/包含）**，比我初稿单一的 adjacency 边列表更贴合
  真实设计语言表达。

### 3.2 商业生成式设计工具（方案阶段输入格式）

| 工具 | 方案阶段输入 | 可借鉴 |
|---|---|---|
| TestFit（地产可研生成） | 地块多边形 + 业态参数（单元配比 unit mix、面积区间、层数、停车指标） | "单元配比"（两房×2/层）比逐房间列表更贴近 plan 粒度 |
| Autodesk Forma / Spacemaker | 地块 + 功能面积指标（各功能总面积、楼层分配） + 规范约束（日照/退线） | 竖向按功能分配面积与楼层 |
| Finch3D / ARCHITEChTURES | 面积表 + 邻接偏好 + 体量约束 | 邻接偏好显式输入 |
| qbiq / Maket（室内） | 房间清单+面积+必须相邻对 | "必须相邻对"最小集表达 |

### 3.3 BIM/交换标准（几何后阶段，供对照）

- **IFC**:`IfcSpace`（空间）+ `IfcZone`（按功能聚合空间，正是"分区"语义）;
  早期设计阶段对应 LOD 100 体块（`IfcBuildingStorey` 标高层级）。v2 的 zone
  命名对齐 IfcZone,bim 阶段衔接更顺。
- **CityJSON / gbXML**：均有 space/zone 两级；gbXML 的 `Space` 带 `zoneIdRef`。

### 3.4 小结（格式维度取舍，★=有论文直接证据）

| 维度 | 候选表示 | 证据/倾向 | 建议 |
|---|---|---|---|
| 竖向分区 | 楼层区间+功能标签（stacking) | 商业工具一致 | **采纳** |
| 分区轮廓 | ①多边形顶点 ②参数化型 ③引用外部文件 | RPLAN 证明轮廓即可驱动全平面；HouseExpo 用线段集+原点约定★ | **①为主，②为便捷别名**，记原点约定，③留扩展位 |
| 面积表 | 类型×数量×面积区间（+占比） | RPLAN 过滤规则即此形态★;TestFit 单元配比 | **采纳**，面积/数量支持区间，支持 per_floor |
| 排布-连通 | 边类型=内门/前门 | HouseGAN++ 照建筑师草图建模★ | **连通边类型化：door / open / front_door** |
| 排布-方位 | 8 向 + side/corner；10 有向关系 | Tell2Design★ / Graph2Plan★ | **8 向词表 + inside/outside** |
| 排布-位置 | 5×5 网格格位 | Graph2Plan★ | **采纳**（粗位置，不给坐标） |
| 排布-包含 | inclusion 关系 | Tell2Design 拓扑三元组★ | **采纳**（中庭/管井内嵌） |
| 强度词表 | must/prefer/avoid | 论文未用；工具用偏好 | 保留但默认 must，见 §6-3 |
| 设计标准 | 引用类型包+键值覆盖 | Forma 规范参数集 | **采纳**，覆盖键对齐类型包 T4 表 |
| 形象表示（人读） | ASCII 竖向分区条 + ASCII 轮廓 + Mermaid 邻接图 | — | **生成式镜像**，非事实源 |

## 4. 轮廓"形象表示"专项

用户特别要求轮廓要"找个方式形象表示"。三个消费者要分开：

- **机器（cad step0/3)**：顶点列表是唯一无歧义事实源（mm，约定原点=地块
  左下角，x 东 y 北，与脚手架坐标系一致）。
- **模型（推理布局）**:`outline_ascii`——把轮廓栅格化成 ASCII（如 2m/格，
  `#`=轮廓内），模型对空间形状的直觉远超对顶点数组的直觉；裙房上塔楼的
  落位关系一眼可读。RPLAN 把户型栅格化为 256×256 图像喂网络，同一条
  思路——栅格视图对"看形状"有效是被验证过的。
- **用户（step2 确认）**:Mermaid 竖向分区图 + ASCII 轮廓，选项框确认时展示。

ASCII 由顶点列表**确定性生成**（脚本固化，写进 scripts/)，不是模型手画——
防止"画错但没人发现"。事实源仍是顶点列表，ASCII 只是视图。

## 5. 结构草案 v2.1（边界审计后：瘦身 plan.json + cad_draft.json)

### 5.1 plan.json v2（瘦身版；定稿即冻结，之后只读）

```jsonc
{
  "version": 2,
  "project": "示例商住楼",
  "site": {
    "lot_polygon_mm": [[0,0],[60000,0],[60000,40000],[0,40000]],
    "origin": "lot_southwest",          // 原点约定(HouseExpo 用质心;我们统一左下)
    "setbacks_mm": {"front": 6000, "rear": 4000, "left": 4000, "right": 4000},
    "north_deg": 0
  },
  "zones": [
    {
      "id": "podium",
      "function": "retail",              // 对齐类型包 id
      "floors": {"from": 1, "to": 3},
      "floor_height_mm": 4800,
      "outline_mm": [[0,0],[60000,0],[60000,40000],[0,40000]],
      "typology_candidates": ["步行街两侧", "中庭环绕"],  // 候选集,拍板在 cad step2
      "program": [
        {"room": "anchor_store", "count": 1, "area_sqm": [1800, 2200]},
        {"room": "shop", "count": [16, 20], "area_sqm": [80, 120]},
        {"room": "atrium", "count": 1, "area_sqm": [300, 400]},
        {"room": "corridor", "min_width_mm": 4000}
      ]
    },
    {
      "id": "tower",
      "function": "residence",
      "floors": {"from": 4, "to": 18},
      "floor_height_mm": 3000,
      "outline_mm": [[18000,22000],[42000,22000],[42000,40000],[18000,40000]],
      "position": {"on": "podium", "align": "north_center"},
      "program": [
        {"room": "unit_2br", "count": 2, "area_sqm": [70, 78], "per_floor": true},
        {"room": "unit_3br", "count": 2, "area_sqm": [92, 98], "per_floor": true},
        {"room": "core", "count": 1, "includes": ["stair","elevator","shaft"]}
      ]
    }
  ],
  "requirements": [
    // 任务书级设计意图:单房间+谓词,不含房间-房间边(那是气泡图,归 cad)
    {"subject": "bedroom", "rule": "faces_south", "strength": "must"},
    {"subject": "bathroom", "rule": "near_core", "strength": "prefer"}
  ],
  "vertical_relations": [
    {"type": "core_continuous", "from": "tower", "through": "podium", "to_ground": true},
    {"type": "roof_use", "of": "podium", "as": "tower_garden"}
  ],
  "standards": {
    "packs": ["retail", "residence"],
    "overrides": {"corridor_min_width_mm": 2400, "accessibility": true}
  }
  // 注意:没有 draft/confirmed——plan 定稿即冻结;迭代状态是 cad 的事
}
```

### 5.2 cad_draft.json v1(cad 侧落盘,原 layout 节与状态机的新家)

```jsonc
{
  "version": 1,
  "source_plan_sha256": "plan.json 定稿哈希",
  "zones": [
    {
      "id": "tower",
      "typology": "central corridor",     // 从 plan typology_candidates 拍板
      "bubble_graph": {
        // 词表来自 §3 论文证据:Tell2Design 拓扑三元组 + HouseGAN++ 门边
        // + Graph2Plan 5×5 格位;面积在 step2 确认后收敛为定值
        "nodes": [
          {"id": "living",  "type": "living",  "area_sqm": 22, "cell": "center_south"},
          {"id": "bedroom1","type": "bedroom", "area_sqm": 13, "cell": "south_row"},
          {"id": "core",    "type": "core",    "cell": "center"}
        ],
        "edges": [
          {"a": "living", "b": "kitchen", "via": "door"},
          {"a": "living", "b": "outside", "via": "front_door"},
          {"a": "bedroom1", "b": "living", "via": "door"},
          {"a": "bedroom1", "b": "bedroom2", "via": "not_through"}   // T0 U-B2 前置
        ],
        "hints": [{"node": "core", "cell": "center"}]
      },
      "requirements_check": [             // plan requirements 的逐条落实说明
        {"rule": "bedroom faces_south", "status": "satisfied", "via": "南排两间卧室"}
      ]
    }
  ],
  "confirmed": false                      // cad step2 用户确认后置 true → 冻结进 step3
}
```

对 v1 的兼容：`building_type` 单值场景 = 单 zone;v1 的 `floors`/`program` 平铺
写法由 step0 归一化为单 zone v2;v1 的 draft/confirmed 语义平移到 cad_draft.json。

## 6. 待定项（修订 plan_contract.md 前需用户拍板，附论文证据倾向）

1. **楼层表示**:`{"from":4,"to":18}` 机器友好，草案已采用。待定：是否允许
   与显式数组混写（如顶层退台的非标层）。
2. **区间值**：面积/数量 `[min,max]` 允许——RPLAN 过滤规则证明区间是 plan 的
   自然表达；cad step2 确认后收敛为定值进 cad_draft（定值才进 building.json)。
3. **强度词表**:must/prefer/avoid 三档，但**默认 must**；论文证据表明连通关系
   更该靠"边类型"(door/front_door）表达；plan 侧 requirements 带 strength,
   cad 侧气泡图的边靠 via 类型表达，不再带 strength。
4. **方位词表**:8 向罗盘（n/ne/e/se/s/sw/w/nw)+ inside/outside + side/corner
   修饰，对齐 Tell2Design，归 cad_draft 词表；plan 侧 requirements 只引用
   其中的谓词（faces_south / near_core)，不引用边关系。
5. **outline_ascii 生成脚本**归 scripts/ 固化，与 canon 同类，step0 调用。
6. v1→v2 硬切换 + step0 自动归一化旧文件。

## 7. 参考来源

一手论文（PDF 已存 `AI_CAD/research/`):
- Wu et al., "Data-driven Interior Plan Generation for Residential Buildings",
  SIGGRAPH Asia 2019 → `AI_CAD/research/rplan_wu2019.pdf`;
  项目页 http://staff.ustc.edu.cn/~fuxm/projects/DeepLayout/index.html
- Hu et al., "Graph2Plan: Learning Floorplan Generation from Layout Graphs",
  ACM TOG 2020, arXiv:2004.13204 → `AI_CAD/research/2004.13204.pdf`
- Nauata et al., "House-GAN++: Generative Adversarial Layout Refinement
  Networks", CVPR 2021, arXiv:2103.02574 → `AI_CAD/research/2103.02574.pdf`
- Li et al., "HouseExpo: A Large-scale 2D Indoor Layout Dataset for
  Learning-based Algorithms on Mobile Robots", 2019, arXiv:1903.09845
  → `AI_CAD/research/1903.09845.pdf`
- "Tell2Design: A Dataset for Language-Guided Floor Plan Generation",
  arXiv:2311.15941 → `AI_CAD/research/2311.15941.pdf`

工具与标准：TestFit / Autodesk Forma / Finch3D 产品文档；IFC4 IfcSpace /
IfcZone / IfcBuildingStorey 语义。链接汇总见 `AI_CAD/research/researchwebsource.md`。

内部：`docs/internal/architecture/ai-bim-agent-page.md` §4.1、
`skills/aidxfv1/references/plan_contract.md` v1、`docs/buildingplan/step_division.md`、
`docs/buildingplan/buildV2/04_plan_boundary_audit.md`(v2.1 边界审计)。
