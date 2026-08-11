# 03 两层对账：设计对账（气泡图↔layout.json)+ 工程对账（layout.json↔DXF)

> 2026-08-06 初版；同日按 06 篇（bim 衔接）修订：layout.json 升为事实源主线、
> DXF 降为工程产物后，原"三路对账（plan 拓扑↔门表↔DXF 实体）"重构为**两层**——
> 门表不再是独立一层，它是 layout.json 的原生字段。
>
> HouseGAN++ 把气泡图的边直接定义成"内门/前门"——关系图与几何产物之间存在
> 可机械核对的不变量。两层对账与 VALIDATION ZONE 同级自动执行：任何一层
> 跑偏都报 FAIL。

## 1. 两层结构

```
cad_draft.json bubble_graph        （设计意图层:模型声明"谁跟谁有门")
        │  求解器展开(确定性)
        ▼
layout.json ★事实源★               （房间多边形/墙段/门表,带语义标签)
   ╱    ╲
 设计对账A:意图↔事实源        工程对账B:事实源↔渲染
 (bubble_graph↔layout.json)   (layout.json↔DXF)
        │                        ▼
        │                     DXF(工程产物,人看,不进下游)
        ▼
   bim 机器消费(ifcopenshell.api 建模)
```

- **对账 A（设计对账）**：模型的设计意图有没有被求解器忠实实现。
  两边都是结构化 JSON，直接字段比对，零几何解析。
- **对账 B（工程对账）**：渲染支线有没有忠实画出事实源。
  DXF 是给人看的工程产物，这里只验证"图没画错"，不验证"设计对不对"。

## 2. 对账规则（全部机械判定）

### A 层：设计对账（bubble_graph ↔ layout.json)

| # | 规则 | 判定方式 | 级别 |
|---|---|---|---|
| A1 | 每条 door 边 ⇔ layout 门表恰有一扇连接 a、b 的门 | 门表查询 | FAIL |
| A2 | 每条 front_door 边 ⇔ 门表有一扇 a→外轮廓的门 | 门表查询 | FAIL |
| A3 | `not_through` 边 ⇔ 门图无 a→b 直达门，且无经私密房间的间接路径（T0 U-B2 机械化） | 门表图遍历 | FAIL |
| A4 | `inside` 关系 ⇔ 房间多边形不接触外轮廓 | 几何判定（shapely) | FAIL |
| A5 | 面积定值 ⇔ 矢量化后房间实算面积 ∈ 容差 | 几何判定 | FAIL |
| A6 | grid_hints ⇔ 房间质心落在声明格位 | 几何判定 | WARN(hint 是软约束） |

### B 层：工程对账（layout.json ↔ DXF)

| # | 规则 | 判定方式 | 级别 |
|---|---|---|---|
| B1 | 门表每扇门 ⇔ DXF A-DOOR 层有一个 swing 实体（位置±容差） | `layout.from_dxf` 反解析比对 | FAIL |
| B2 | 每个 swing 所在墙段两侧房间 = 门表声明的两侧房间 | 同上 | FAIL |
| B3 | layout 墙段集 ⇔ DXF A-WALL 实体集（端点±容差） | 同上 | FAIL |
| B4 | 朝向约束（faces south) ⇔ 房间在南向外墙有开洞 | 几何判定 | WARN（尽力而为） |

### 类型规则（R9+，挂 A 层之后）

hub_connect/public_placement 等类型谓词实例编译出的对账规则（见
`architecture.md` §3.2 映射表），对 layout.json 判定，FAIL 级。

## 3. 实现位置

- 门表是求解器的**原生输出**（layout.json 字段），A 层对账是纯 JSON 比对，
  成本极低。
- B 层依赖 `layout.from_dxf`（DXF→图反解析），与模板检索（02 §1）共用
  同一实现。
- 执行顺序（S3 内）:③-4 落盘 → A 层设计对账 → ③-5 渲染 → B 层工程对账
  + VALIDATION ZONE（v1 几何规则，对 DXF 照跑，双保险——渲染器理论上
  不产生这些错，但校验器不假设这一点）。全部 0 FAIL 才进 S4。
- 报告格式沿用 `[validate]` 风格，分两层前缀：
  `[reconcile:design] A1 FAIL: door living↔kitchen declared but missing in door table`
  `[reconcile:eng] B1 FAIL: door at (4200,3000) in table but no A-DOOR entity`

## 4. 对 v1 校验体系的归并关系

| v1 现有 | v2 去向 |
|---|---|
| VALIDATION ZONE 几何规则（U-A1/A2/A3、U-D1/D3) | 保留，B 层阶段对 DXF 照跑 |
| BY REVIEW 项（U-B 连通、U-C 隔离） | A3/A4 机械化的部分升级为 FAIL；其余（公私分区语义）仍 BY REVIEW，但审查对象是气泡图——**审查从几何上移到关系层** |
| canon 字节级重现 | 保留且**双轨**:layout.json 与 DXF 各自字节级重现（求解器 fixed seed 保证同解） |

## 5. 待定项

1. A3 的路径遍历深度：卧室⇔卧室无门且无经由另一卧室的间接路径；经由
   客厅/走廊合法——房间类型分类（私密/公共）从类型包 room_attrs 取。
2. B4 朝向判定"南侧"容差：开洞中心在南向 ±45° 区间？待与类型包 T4 对齐。
3. ~~门表是否随 building.json 交付 bim~~ → **已定**:building.json 含
   doors[] 门表 + 每层 layout.json 路径与 sha256(06 篇 §4.1)。
