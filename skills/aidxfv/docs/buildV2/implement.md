# buildV2 执行清单

> 2026-08-06。依据 `architecture.md`（总装配）+ 01-05 各篇调查。
> 默认假设（用户可推翻）：OR-Tools+shapely 依赖接受；栅格默认 250mm、类型包可覆盖；
> 房间允许 L 形；模板库=skill 种子+项目增长双库；building.json 含 doors[];
> 类型包 .md 与 .rules.json 手工双写 + 同源校验脚本。

## P0 契约层（一切的前提，纯文本）

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 0.1 | plan.json v2.1 + cad_draft.json v1 正式契约 | `skills/aidxfv2/references/plan_contract.md` 重写 | 含字段表/状态机/缺失处理；与 buildV2 v2.1 草案一致 | — |
| 0.2 | 两份 JSON Schema | `references/schemas/plan.schema.json`、`cad_draft.schema.json` | 合法样例通过、缺硬约束样例被拦 | 0.1 |
| 0.3 | 金样 plan+cad_draft（示例商住楼，来自 research §5) | `references/examples/plan_demo.json`、`cad_draft_demo.json` | 过 0.2 schema 校验 | 0.2 |

## P1 反编译器（模板库与对账的共用底座）

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 1.1 | `layout.from_dxf`:archdxf 产 DXF → 气泡图/几何 JSON。**三处复用：模板反编译 / B 层工程对账 / bim 前同步桥（06 §7)** | `scripts/packages/layout/src/layout/from_dxf.py` | v1 三金样反编译：房间数/门边/轮廓与原文档一致；确定性（两次解析同输出）;不可解析实体（自造图层/手绘线）报坐标不静默丢弃 | 0.1 |
| 1.2 | 三金样反编译报告（"反面教材体检"） | 附在 1.1 测试里输出 | residence_1br 的 U-C 隔离问题（卫生间门对厨房？）被报告点名 | 1.1 |

## P2 类型包 v2（两份先行）

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 2.1 | 谓词词表定稿（~10 个） | `references/predicate_vocabulary.md` | hub_connect/public_placement/not_through/near/faces/at_end/inside/… 每个有 CP-SAT 编译规则+对账规则 | 0.1 |
| 2.2 | `residence.rules.json` + residence.md v2 | 房间属性表/规则实例/预锁配置/权重表/粒度覆盖 | 表达得出：客厅枢纽、卧室朝南、卫生间贴管井、穿套禁忌 | 2.1 |
| 2.3 | `office.rules.json` + office.md v2 | 同上 | 表达得出：核心筒预锁、环廊 hub_connect、疏散楼梯 public_placement、办公房采光面 | 2.1 |
| 2.4 | 同源校验脚本：.md 与 .rules.json 漂移检查 | `scripts/` 内 | 改 json 不改 md（或反之）时报漂移 | 2.2/2.3 |

## P3 求解器本体（心脏）

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 3.1 | 栅格化器：轮廓多边形 → 单元集 + 邻接 + 外边界标记 + 预锁定格 | `layout/raster.py`(shapely) | 直角多边形全覆盖无重叠；预锁格标记正确 | 2.1 |
| 3.2 | CP-SAT 求解器：通用硬约束 + 谓词编译 + 目标权重 | `layout/solve.py`(ortools) | ①住宅 1 居（residence 规则）解出客厅连通各房、南卧；②办公小层解出环廊贴核心筒；③fixed seed 两次求解同解 | 2.1-2.3、3.1 |
| 3.3 | UNSAT 诊断：slack 逐约束重跑 → 冲突约束清单 | solve.py 内 | 面积超轮廓/环互斥邻接两个案例，报告指认正确约束 | 3.2 |
| 3.4 | 矢量化：单元并集 → 房间多边形 → 墙段 → 门位（100mm snap) | `layout/vectorize.py`(shapely) | 面积回填仍在区间；door 边两侧确有公共边界；L 形保留 | 3.2 |
| 3.5 | **A 层设计对账**(A1-A6：气泡图↔layout.json 纯 JSON 比对） | `layout/reconcile.py` | 人为破坏气泡图/门表各一次，对应规则报警 | 3.4、3.8 |
| 3.6 | 类型对账 R9+：谓词实例 → 对账规则编译（挂 A 层） | reconcile.py 内 | hub_connect/public_placement 正反例各一 | 2.2-2.3、3.5 |
| 3.7 | **B 层工程对账**(B1-B4:layout.json↔DXF，经 from_dxf 反解析）+ v1 VALIDATION ZONE 照跑 | reconcile.py 内 + archdxf 渲染器 | 人为破坏 DXF 门/墙各一次，B1/B3 报警 | 1.1、3.4、4.2 |
| 3.8 | layout 输出落盘契约（bim 数据源，06 篇）:`<floor>.layout.json` = 房间多边形（带 type)+墙段+门表+预锁标记；building.json floors[] 加 layout 路径+sha256 | `layout_output.schema.json` + vectorize.py 落盘 | 过 schema；与 DXF 同源一致（B 层对账可核） | 3.4 |
| 3.9 | 金样回归：residence_1br 经求解管线重生成，layout.json 与 DXF **双轨** canon 字节级重现 | `tests/golden/` | 与 v1 金样机制同构 | 3.4-3.7 |

## P4 管线接线（steps + scaffold v2)

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 4.1 | `steps/` 五文件按 architecture §1/§4 改写（S0 路由/schema 校验停步/confirmed 冻结） | `skills/aidxfv2/steps/` | 中断恢复三态路由正确 | 0.1-0.3、P3 |
| 4.2 | scaffold v2 + DXF 渲染器：DECLARATION ZONE 只填气泡图；管线自动走 求解→layout.json（主线）→archdxf 渲染 DXF（支线）;VALIDATION ZONE 照跑 | `references/scaffold_floor_plan.py` v2 + `layout/render_dxf.py`（调 archdxf) | 只填气泡图即产 layout.json + DXF；渲染器零独立逻辑（纯 layout.json→archdxf 调用） | 3.4、3.8 |
| 4.3 | SKILL.md：路由表 + 类型包孪生纪律 + 依赖声明 | `SKILL.md` | 新会话仅读 SKILL.md 能正确起步 | 4.1-4.2 |
| 4.4 | outline_ascii 生成脚本 | `scripts/` 内 | 塔楼落裙房的 ASCII 图一眼可读 | 0.3 |
| 4.5 | **bim 前同步桥**(06 §7 协议）:DXF 哈希比对 → 已变则 from_dxf 再生 layout.json → 新旧 diff 审计报告 → A 层对账重跑 → 0 FAIL 放行/有 FAIL 出裁决报告 | `layout/sync.py` | ①未编辑走快速路径；②模拟人工移动一扇门：diff 报告点名该门、A 层仍过；③模拟手画线破坏：不可解析实体报坐标 | 1.1、3.5、3.8 |

## P5 模板库（可与 P3/P4 并行）

| # | 任务 | 产出 | 验收 | 依赖 |
|---|---|---|---|---|
| 5.1 | `layout.from_zind` 解析器 | from_dxf 同族 | ZInD 样本→气泡图 JSON | 1.1 |
| 5.2 | 人工精选首批设计模板（residence/office 各 2-3) | `references/templates/*.json` | 每个过人工评审记录；烂的不进 | 5.1 |
| 5.3 | 相似度检索器（function 过滤+轮廓/房间多重集/拓扑距离排序 top-3) | `layout/retrieve.py` | 给定塔楼轮廓，住宅模板排在商场前 | 5.2 |
| 5.4 | S4 飞轮：交付时 layout_graph.json 落盘 + `template_worthy` 人工门 | step-04 修订 | 未标记不入库 | 4.1、5.3 |

## 顺序与里程碑

```
P0(契约) ──► P1(反编译) ──► P2(类型包) ──► P3(求解器) ──► P4(接线)
                                    └──────► P5(模板库,并行) ──┘
M1 = P0 完成(契约冻结)   M2 = P3.2 首次 SAT(住宅 1 居解出)   
M3 = P4 完成(端到端:plan.json → DXF)   M4 = P5.3 检索接入 S1
```

每个 P 内部按编号顺序；跨 P 只看依赖列。全部任务遵循：先写失败测试
（反例）再实现；确定性（fixed seed/canon）是每个任务的隐含验收。
