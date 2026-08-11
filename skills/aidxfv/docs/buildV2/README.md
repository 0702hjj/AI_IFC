# buildV2 —— aidxfv2 构建调查中枢

> 2026-08-06。v2 的颠覆点：**模型画关系图、机器算几何、机器对账**。
> 论文证据见 `plan_format_research.md` §3.1(RPLAN / Graph2Plan / HouseGAN++ /
> Tell2Design 一手精读,PDF 在 `research/`)。
> 本目录是 v2 的设计调查与决策记录,每篇一个主题,含论文证据、方案对比、选型结论。

## 总体架构(v1 → v2)

```
v1: 模型声明坐标 → 脚手架展开 → 校验器挑错(FAIL 循环)
        ↑ 模型碰几何,防越界靠校验+纪律

v2: plan.json(轮廓+面积表+规范)
        │
        ├─ ① 模板检索(Graph2Plan):金样库找最近布局图,改造起步
        │
        ├─ ② 布局求解器(心脏):轮廓 × 气泡图 × 面积区间
        │      → 栅格房间划分(RPLAN/HouseGAN 同款 raster 中间态)
        │      → 矢量化 → 房间多边形 + 墙段 + 门位
        │
        ├─ ③ layout.json 落盘 ★事实源★(房间/墙段/门表+语义标签)
        │      ├─► bim 阶段机器消费(→ ifcopenshell.api 建模)
        │      └─► archdxf 画法库(v1 资产):渲染 DXF
        │            DXF = 工程产物,给人/前端看,不是机器数据源
        │
        └─ ④ 两层对账:设计对账(气泡图↔layout.json)
                     + 工程对账(layout.json↔DXF 渲染保真)
        模型全程不碰坐标;坐标全部来自确定性求解器
```

## 文件索引

| 文件 | 主题 | 状态 |
|---|---|---|
| `architecture.md` | **总装配图**:step 级完整运行流程 + 按类型改变求解的操作板块 | 本文，待拍板（§6 清单） |
| `plan_format_research.md` | plan 落盘格式调研（5 篇论文精读）+ plan.json v2.1 / cad_draft.json 契约草案 | v2.1 已按边界审计修订 |
| `01_layout_solver.md` | **心脏**：布局求解器——空间划分算法调查与选型 | 调查完成，待拍板 |
| `02_template_retrieval.md` | 模板检索：金样 DXF → 布局图 → 相似度检索起步 | 调查完成，待拍板 |
| `03_reconciliation.md` | 两层对账：设计对账（气泡图↔layout.json)+ 工程对账（layout.json↔DXF) | 已按 06 篇重构 |
| `04_plan_boundary_audit.md` | plan 职责边界审计：layout.* 与状态机移出 plan.json | 已执行（research 文档 v2.1) |
| `05_reference_libraries.md` | 参考库调查：OR-Tools/shapely 采用，ZInD 模板种子，许可证双门 | 调查完成，已回写各篇 |
| `06_bim_alignment.md` | cad→bim 衔接：bim 消费 layout.json 而非 DXF;ifcopenshell 2D 能力实测 | 调查完成，已回写 implement |
| `implement.md` | **执行清单**:P0-P4 主线 + P5 并行，任务/产出/验收/依赖/里程碑 | 待开工 |

## 关键设计立场(继承 v1,不因架构升级而松动)

1. **确定性**:求解器必须可复跑(fixed seed),产物过 canon 字节级重现——
   与 v1 金样机制同构。
2. **可解释的失败**:求解失败(约束冲突)必须输出**哪几条约束打架**,
   回喂模型改气泡图——错误信息即教材(C 防线)在 v2 的形态。
3. **模型仍有设计权**:气泡图、面积表、模板选择、求解结果的 BY REVIEW
   取舍都是模型的;被机器拿走的只有坐标计算。
4. **v1 资产全复用**:archdxf 画法库、T0 通用标准、类型包、canon、
   VALIDATION ZONE 校验器(求解产物仍需过同一套几何校验,双保险)。
5. **算法复用优先于自研**:引入依赖需过双门——许可证(宽松/无传染)+
   活跃度(近一年有提交)。已选定:OR-Tools(Apache-2.0)、shapely(BSD-3),
   见 `05_reference_libraries.md`。
