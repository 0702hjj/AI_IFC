# aidxfv2 运行流程架构（step 级）

> 2026-08-06。本文是 v2 的总装配图：从 plan.json 进来到 building.json + DXF 出去的
> 完整运行流程，step 级拆解，含**按 building_type 改变求解行为**的操作板块。
> 依据：`plan_format_research.md`(v2.1 契约)、`01_layout_solver.md`(求解器选型)、
> `02_template_retrieval.md`(模板检索)、`03_reconciliation.md`(三路对账)、
> `04_plan_boundary_audit.md`(职责边界)。

## 0. 全流程总览

```
                    ┌────────── 机器(确定性) ──────────┐ ┌──── 模型(LLM) ────┐ ┌─ 用户 ─┐

plan.json(冻结) ──► S0 摄取校验 ──► S1 草案 ──► S2 确认 ──► S3 求解构建 ──► S4 交付
                       │              │           │            │             │
                     校验器        检索+起草     选项框      求解器        对账+落盘
                     [机器]       [机器+模型]   [用户]      [机器+模型]    [机器]
                                      ▲                        │
                                      └── FAIL 回喂(改气泡图) ○┘

S3/S4 产物双轨:layout.json = 事实源主线(bim 机器消费)
              DXF        = 工程产物支线(用户/前端浏览,archdxf 渲染自 layout.json)
```

铁律（继承 v1，见 README 设计立场）：**模型只碰关系（气泡图/面积/规则实例），
机器算全部坐标；任何 FAIL 不许解释过去，必须改输入重跑。**

## 1. Step 级流程

### S0 摄取与校验（机器为主）

| 项 | 内容 |
|---|---|
| 输入 | plan.json v2.1（瘦身版，定稿冻结） |
| 机器动作 | ① schema 校验（脚本固化，不许模型目测）;② 算术预检：各 zone 面积需求合计 vs 轮廓可用面积，超界直接报"超 X%";③ vertical_relations → 派生预锁定集（核心筒/楼梯/电梯井的占位指令）;④ `outline_ascii` 生成（顶点→ASCII 视图，供模型与用户看形状） |
| 模型动作 | 读 plan + T0 + `standards.packs` 指定的类型包 .md，语义理解设计意图 |
| 输出 | 校验通过的 plan 视图 + 每 zone 的预锁定集 + ASCII 轮廓 |
| 停步条件 | 硬约束缺失/面积矛盾未解决——S0 是唯一允许空手等用户的步骤 |
| 路由 | plan 无对应 cad_draft.json → S1；有未确认 draft → S2；已 confirmed → S3 |

### S1 草案（模型起草，机器辅助）

| 项 | 内容 |
|---|---|
| 输入 | plan 视图 + 类型包 + **模板库检索结果** |
| 机器动作 | 模板检索（02)：按 function 过滤 → 轮廓相似度+房间多重集+拓扑距离排序 → top-3 模板的气泡图 |
| 模型动作 | ① 从 top-3 选模板（或声明从零起草）;② 改造气泡图：调房间数/面积定值化（区间→定值，可留到 S2 由用户拍）/增删边；③ 从 plan.typology_candidates 选 typology;④ 实例化类型包规则（§3);⑤ 逐条写 requirements_check(plan 的 requirements 如何落实）;⑥ 写 deviations / defaults_used（隐瞒即违规） |
| 输出 | `cad_draft.json`(confirmed: false) |
| 完成条件 | 气泡图节点⊇program 房间清单；每条 requirements 有落实说明；规则实例全部来自类型包词表 |

### S2 交互确认（用户拍板）

| 项 | 内容 |
|---|---|
| 输入 | cad_draft.json(confirmed: false) |
| 交互 | 选项框逐条：typology 选择、面积定值（区间内拍定）、每条 deviation、每个 defaults_used、气泡图整体（Mermaid 邻接图 + ASCII 轮廓展示） |
| 输出 | cad_draft.json 修订 + `confirmed: true` → **冻结** |
| 铁律 | 冻结后任何设计修改回到 S2 重确认；S3 无权改设计，只有求解权 |

### S3 求解与构建（机器为主体，模型处理失败回喂）

每 zone × 每层类型执行（同构楼层只解一次，标准层复用）:

```
③-1 编译:气泡图 + 类型规则实例 + 预锁定集 → CP-SAT 模型(约束+目标)   [机器]
③-2 求解:fixed seed,一次全量解                                       [机器]
      ├─ UNSAT → slack 逐约束重跑定位冲突 → 回喂模型改气泡图 → 回 S1 修订
      └─ SAT  → 栅格分配图(每格一个房间标签)
③-3 矢量化:单元边界追踪 → 房间直角多边形 → 墙段 → 门位(100mm snap)   [机器]
③-4 layout.json 落盘 ★主线事实源★:房间(带类型)/墙段(带两侧房间)/
      门表/预锁标记,过 layout_output.schema.json                     [机器]
      ├─► 设计对账:气泡图拓扑 ↔ layout.json(R1/R2/R5/R6/R8 + 类型 R9+)
      │    FAIL → 回喂 → 回③-1(参数级)或 S1(设计级)
      └─► 工程渲染支线:
③-5   archdxf 消费 layout.json 出 DXF(墙/开洞/门 swing/楼梯/标注)   [机器]
      DXF = 工程产物,给人/前端看;不是机器数据源,不参与下游链路
③-6 工程对账:layout.json ↔ DXF 渲染保真(R3/R4 改为 layout↔DXF 核对)
      + VALIDATION ZONE(v1 几何规则,对 DXF 照跑)                    [机器]
③-7 canon:layout.json 与 DXF 双确定性(字节级重跑比对)               [机器]
```

模型在 S3 的唯一动作：**读失败回喂，决定改什么**（放宽面积区间/删改一条边/
换格位 hint），绝不直接改坐标、改图。

### S4 交付（机器）

两类产物，两类消费者：

| 产物 | 消费者 | 内容 |
|---|---|---|
| `building.json` + `<floor>.layout.json` | **bim 阶段（机器）** | floors(elevation/height/sha256)+ 每层 layout.json 路径+哈希；doors[] 门表；metadata(DXF 不承载的材质/occupancy) |
| `<floor>.dxf` | **用户/前端（人）** | 工程图纸，渲染自 layout.json，可独立浏览，不参与下游 |
| `layout_graph.json` | **模板库（飞轮）** | 气泡图落盘，`template_worthy` 人工门后入库 |

一致性自检（layout↔DXF 对账通过、路径/哈希/层数与 plan 对齐）后向用户报告。

## 2. 求解器通用内核（类型无关）

```
输入:轮廓多边形 + 气泡图 + 预锁定集 + 规则实例集 + 目标权重表
    │
    ▼ 栅格化(250-500mm 单元,类型包 T4 可覆盖)
格子 × 房间 的 Bool 分配变量
    │
    ▼ 通用硬约束(恒成立,与类型无关)
  · 每格恰属一个房间(或走廊余量)
  · 房间面积(格数)∈ 面积区间
  · 房间区域连通(无飞地)
  · 预锁定格固定(核心筒/楼梯)
  · door 边 ⇒ 两房间共享边界;front_door ⇒ 贴外轮廓
  · inside ⇒ 不贴外轮廓;not_through ⇒ 无门边
    │
    ▼ 目标函数 = Σ(类型权重 × 评分项)   ← 类型差异的唯一注入口之一
    │
    ▼ CP-SAT 求解 → 栅格分配 → 矢量化 → layout.json(事实源)
                                          └─► archdxf 渲染支线 → DXF(工程产物)
```

## 3. 按 building_type 改变求解（操作板块）

**原则：求解器不认识建筑类型。类型的全部特殊性 = 四份数据**，在 ③-1 编译时注入：

### 3.1 数据一：房间属性表（T2 词汇的机器化）

每个房间类型一行属性，谓词编译时引用：

```jsonc
// office.rules.json 节选
"room_attrs": {
  "office":   {"privacy": "private", "needs_exterior": true,  "wet": false},
  "toilet":   {"privacy": "public",  "needs_exterior": false, "wet": true},
  "corridor": {"privacy": "public",  "needs_exterior": false, "hub": true},
  "stair_evac":{"privacy": "public", "needs_exterior": false, "prelocked": true},
  "meeting":  {"privacy": "shared",  "needs_exterior": true,  "wet": false}
}
```

`needs_exterior: true` → 编译为"该类房间必须有格子贴外轮廓"（采光面）;
`hub: true` → 枢纽评分项激活；`wet` → 湿区聚拢评分项（贴管井）激活。
**同一属性在不同类型取值不同**：住宅 bedroom needs_exterior=true、商场
shop needs_exterior=false（面向内街即可）——求解行为因此分叉。

### 3.2 数据二：规则实例集（类型包 T7 扩容，拓扑谓词）

谓词词表通用且固定（~10 个），类型包只给**实例**:

| 谓词 | residence 实例 | office 实例 | retail 实例 |
|---|---|---|---|
| `hub_connect(hub, members)` | hub=living, members=[bedroom.*, kitchen] | hub=corridor, members=[office.*, toilet.*, meeting.*] | hub=arcade, members=[shop.*, anchor] |
| `public_placement(room, not_inside)` | — | stair_evac ∉ office.* | 疏散楼梯 ∉ shop.* |
| `not_through(a, b)` | bedroom↔bedroom | office↔office | shop↔shop（各自向 arcade 开门） |
| `near(a, b, strength)` | bathroom near shaft (prefer) | toilet near core (must) | — |
| `at_end(a, of)` | — | — | anchor at_end of arcade |
| `faces(room, dir, strength)` | bedroom/living faces south (must/prefer) | — | anchor faces main_street |

编译映射（谓词 → CP-SAT 约束 / 对账规则）:

- `hub_connect` → 每个 member 与 hub 共享边界（或有门链 ≤2 跳）→ R9 对账：图遍历验证
- `public_placement` → 目标区域有边贴公共区域 + 不被 not_inside 类型围合 → R10
- `not_through` → 门图无边 + 无经私密房间的路径 → R5（通用已含）
- `faces` → 房间贴指定 ±45° 方位外轮廓且有开洞 → R7（通用）

### 3.3 数据三：预锁定集（从 vertical_relations + 类型包派生）

核心筒/楼梯/电梯井/管井 = 障碍格，求解前固定，不参与分配：

- office：核心筒整体预锁（电梯+双楼梯+管井），位置由 plan.position + grid hint 定
- residence：楼梯间+管井预锁（多层对齐约束：各层预锁格坐标必须一致——
  这是竖向对齐的机械保证，03 R-系可校验）
- retail：中庭空洞+扶梯井预锁；主力店**不预锁**（参与求解，at_end 规则塑形）

### 3.4 数据四：目标权重表（"什么算好布局"的类型答案）

通用评分项 × 类型权重（0 = 该项不参与）:

| 评分项 | residence | office | retail |
|---|---|---|---|
| 枢纽居中（hub 质心近轮廓质心） | 1.0（客厅居中，RPLAN★) | 0.8（走廊成环/成轴） | 1.0（中庭居中） |
| 朝南房间数 | 1.0 | 0（办公不讲究朝向，讲采光面） | 0 |
| 采光面利用（needs_exterior 房间贴边长度） | 0.6 | 1.0（办公房最大化贴窗） | 0.2 |
| 湿区聚拢（wet 房间互邻） | 0.8 | 0.8 | 0.3 |
| 走廊总长度（越小越好） | 0.4 | 1.0（得房率） | 0（商场走廊是空间本体） |
| 展示面（shop 贴 arcade 边界长度） | 0 | 0 | 1.0 |
| 房间矩形度（L 形惩罚） | 0.3 | 0.6（办公方正） | 0.5 |

同一组格子、同一个求解器，**权重表一换，解的形态完全不同**：
住宅解出"客厅居中+南排卧室"，办公解出"核心筒+环廊+四周办公"，
商场解出"中庭+两侧铺面"——这就是"按类型直接改变算法求解"的落点：
**不改算法，改算法的输入数据（约束实例+预锁集+目标）。**

### 3.5 无类型包时的行为

plan.standards.packs 指定的类型无包 → 只用 T0 + 通用硬约束 + 默认权重
（矩形度 0.5，其余 0),S1 必须显式声明"无包求解，BY REVIEW 责任在模型"，
S2 用户确认时突出提示。

### 3.6 新类型规则的沉淀（飞轮）

项目中发现的新规则 → 模型用语义理解起草 → 该项目 BY REVIEW 执行 →
验证后写入类型包 `xxx.rules.json` + .md 采纳日志 → 下次编译为机械约束。
与模板库飞轮（02）并列：**规则库与模板库双轮增长**。

## 4. 状态与恢复

| 落盘文件 | 职责 | 状态字段 |
|---|---|---|
| plan.json | 意图事实源（plan 阶段产物） | 无——定稿即冻结 |
| cad_draft.json | cad 设计事实源 | confirmed: false/true |
| building.json + DXF + layout_graph.json | 交付事实源 | sha256 自校验 |

中断恢复：S0 重载全部落盘，按"无 draft→S1 / 未确认→S2 / 已确认→S3"路由，
不依赖会话记忆（架构文档 §4.4 统一加载约定）。

## 5. 实现落点（skills/aidxfv2）

```
skills/aidxfv2/
├─ steps/                    step-00..04(S0 路由按本文 §4 修订)
├─ references/
│  ├─ plan_contract.md       plan.json v2.1 + cad_draft.json v1 正式契约
│  ├─ schemas/               plan/cad_draft/layout_output 三份 JSON Schema
│  ├─ building_types/
│  │  ├─ office.md + office.rules.json      类型包 v2:.md(模型读)+ .rules.json(机器读)
│  │  └─ ...
│  └─ scaffold_floor_plan.py v2:气泡图声明 → 调 layout → 产 layout.json + DXF
└─ scripts/packages/
   ├─ archdxf/               v1 画法库,零改动;v2 角色=layout.json 的 DXF 渲染器
   └─ layout/                v2 新包:栅格化/CP-SAT 求解/矢量化/layout.json 落盘/
                             对账/模板检索;零 ezdxf 依赖(算几何的不知道图纸)
```

产物定位（S4 双轨）:**layout.json = 事实源主线**（过 layout_output.schema,
bim 阶段机器消费的唯一输入）;**DXF = 工程产物支线**(archdxf 渲染自
layout.json，供用户/前端浏览，不参与任何下游机器链路）。详见
`06_bim_alignment.md`。

## 6. 待拍板清单（汇总各篇）

1. OR-Tools CP-SAT 依赖（纯 wheel,Apache-2.0)→ **05 调查建议接受**;
   shapely(BSD-3）作矢量化依赖；备选纯 Python SA 仅在拒绝依赖时启用（01 §5.1)
2. 栅格粒度：统一 250mm，还是类型包 T4 可覆盖（住宅 250 / 商业 500)?(01 §5.2)
3. 房间允许 L 形（倾向允许）?(01 §5.3)
4. 模板库落盘：skill 内置种子 + 项目侧增长，两库并存？(02 §6.1)
5. building.json 是否含 doors[] 门表（倾向含，供 bim IfcDoor)?(03 §5.3)
6. 类型包 .md 与 .rules.json 同源维护方式：手工双写 or .md 内嵌 json 块单写？(本文 §3)
