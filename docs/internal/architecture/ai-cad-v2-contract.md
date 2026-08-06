# AI CAD v2 契约：cad 落盘产物与 workflow / 网页编辑工具的对齐规范（2026-08-06）

> 面向：**workflow 串联 + DXF/BIM 网页二次编辑工具**的开发者。
> 本文把 AI_CAD 侧 v2 管线（`AI_CAD/docs/buildingplan/buildV2/`，设计已定稿、
> 未实现）中与平台侧协作的契约抽出来：你需要消费什么、遵守什么、谁来提供什么。
> 上游架构背景见 `ai-bim-agent-page.md` §4（plan/cad/bim 三入口、§4.4 统一加载约定）。

## 1. 一张图看懂位置

```
plan skill → plan.json ──┐
                         ▼
              cad skill(aidxfv2, AI_CAD)  ← 你不需要管内部求解细节
                         │
                         ├─► layout.json ★机器事实源★ ──► bim(ifcopenshell.api 建模)
                         │         ▲                            │
                         ├─► building.json(竖向/门表/哈希)      │ ifcopenshell.draw
                         │         │                            ▼
                         └─► DXF(工程产物)──► 用户/前端浏览编辑   图纸级回归验证
                                   │
                                   └── 你的 DXF 网页编辑工具在这
```

**核心约定：DXF 是给人看的工程产物，不是机器数据源。任何下游机器链路
（bim 建模）只消费 layout.json + building.json。**

## 2. 落盘产物清单（你的 workflow 要搬运/加载的文件）

| 文件 | 生产者 | 消费者 | 内容要点 |
|---|---|---|---|
| `plan.json` v2.1 | plan 阶段 | cad S0 | 意图事实源：site/zones(功能/楼层区间/轮廓/面积表)/requirements/standards。**定稿即冻结，无状态字段** |
| `cad_draft.json` v1 | cad S1 | cad S2(用户确认） | 气泡图（房间节点+门边+格位 hint)+ requirements_check + `confirmed` 状态机 |
| `<floor>.layout.json` | cad S3 | **bim 建模（唯一几何输入）** | 每层：房间直角多边形（带类型）/墙段（带两侧房间）/门表（带 via 类型）/预锁标记。过 `layout_output.schema.json` |
| `building.json` v2 | cad S4 | bim + workflow | floors[](name/elevation/height/**dxf 与 layout 双路径+双 sha256**)/doors[] 门表/metadata |
| `<floor>.dxf` | cad S3 渲染支线 | **人 + 前端 + 你的编辑工具** | archdxf 图层纪律的工程图纸 |
| `layout_graph.json` | cad S4 | 模板库 | 气泡图落盘（检索复用） |

JSON Schema 由 cad 侧提供（`skills/aidxfv2/references/schemas/`,implement P0);
workflow 加载时可直接用 schema 校验（jsonschema pip 包）。

## 3. DXF 网页编辑工具的纪律（最重要的一节）

你的编辑工具消费和回写 DXF。从 dxf 能**无损逆向解析**出 layout.json 的前提，
是编辑不越出 archdxf 图层约定：

| 图层 | 内容 | 编辑语义 |
|---|---|---|
| `A-WALL-EXTR` / `A-WALL-INTR` | 外墙/隔墙双线+开洞盖掩 | 移墙=改墙段实体 |
| `A-DOOR` | 门 swing(1/4 弧+门板线） | 移门/改向=改 swing 实体，**不要删弧重画** |
| `A-GLAZ` | 窗 | 同上 |
| `A-COLS` | 柱 | — |
| `A-STRS` | 楼梯符号 | — |
| `A-ANNO-TEXT` | **房间名标注（语义来源！)** | 房间改名=改 text；删标注=丢房间语义 |
| `A-DIMS` | 尺寸链 | 从动，可重生成 |

**工具实现要求**:

1. 编辑操作请基于**构件**（选中一扇门=选中 A-DOOR 组），不要退化成自由
   画线；新增构件走 archdxf 画法（cad 侧可提供调用或生成服务）。
2. 用户手画了不合规实体（自造图层/自由线）→ 逆向解析会报
   **"不可解析实体 + 坐标"**，工具应提示用户修正，而不是静默带过。
3. 尺寸标注/房间面积后缀（`M2`）等从动信息，编辑后由 cad 侧重生成，
   工具不必维护。

## 4. 同步桥协议（bim 启动前，workflow 负责触发）

人工编辑过的 DXF 会让交付时的 layout.json 过期。bim 消费前必须走同步桥
（cad 侧提供 `layout/sync.py`,implement P4.5):

```
① 重算 DXF sha256,与 building.json 记录比对
   ├─ 未变 → 快速路径:直接用交付时 layout.json
   └─ 已变 → ② layout.from_dxf(编辑后 DXF) → 再生 layout.json
             ③ 新旧 diff → 审计报告(人改了什么:墙位移/门增删/房间改名)
             ④ A 层设计对账重跑(断连通/穿套/面积出界?)
                ├─ 0 FAIL → 放行,building.json 哈希刷新
                └─ 有 FAIL → 出裁决报告给用户(改图 or 显式豁免,豁免入 metadata)
```

- `from_dxf` 解析器**只有一份，在 cad 侧**(skills/aidxfv2 layout 包）。
  平台/工作流侧不要平行实现第二个——双实现必漂移，对账体系会崩。
- 同步桥的输出（再生 layout.json + diff 报告）建议作为 workflow 的可视化
  节点呈现：人改了什么、有没有破坏设计规则，一目了然。

## 5. bim 侧对齐（你串联到 aiifc/edit-service 时的接口）

- 建模输入：`layout.json`（几何+语义）+ `building.json`（竖向标高/门表/
  metadata)。转换方式=确定性脚本（架构文档 §4.3.6"脚本式转换→设计参数
  参考→ifcopenshell.api 建模"),cad 侧保证 layout.json 的 schema 稳定与
  字节级可重现（fixed seed + canon)。
- **不要从 DXF 反解建模**:ifcopenshell 无 DXF 识图器（实测，06 篇）;
  门表/房间类型/标高也不在 DXF 里。
- 回归验证：bim 产出 IFC 后可用 `ifcopenshell.draw` 反出 SVG 平面图，
  与 cad DXF 做图纸级比对（这是 draw.py 在链路的正确用法）。
- 编辑流对接：人/AI 双角色编辑 API 不变；AI 直连 edit-service 传
  `provenance.source="AI"`。

## 6. 分工边界（谁提供什么）

| 提供方 | 内容 |
|---|---|
| **cad 侧（AI_CAD/aidxfv2)** | 三份 JSON Schema;layout 包（求解/矢量化/from_dxf/sync);archdxf 画法库与图层纪律文档；对账器；canon 确定性机制 |
| **平台侧（你）** | workflow 串联（落盘文件加载/搬运/版本）;DXF 网页编辑工具（遵守 §3 构件纪律）;同步桥触发与裁决 UI;bim 建模脚本与 IFC 交付 |

## 7. 深入阅读（AI_CAD/docs/buildingplan/buildV2/)

`architecture.md`（总装配,step 级）· `plan_format_research.md`（契约 v2.1
草案）· `01_layout_solver.md`（求解器）· `03_reconciliation.md`（两层对账）·
`05_reference_libraries.md`（依赖）· `06_bim_alignment.md`(bim 衔接+同步桥）·
`implement.md`(P0-P5 执行清单）
