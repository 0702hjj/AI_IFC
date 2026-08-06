# 06 cad → bim 衔接衡量：V2 产物 vs DXF vs ifcopenshell 2D 能力

> 2026-08-06。问题：V2 后续对齐 IFC 生成（bim/aiifc skill）时，消费什么形态的
> 产物？用户判断"框定二维坐标不能直接消费 DXF，最好是有标记+空间坐标的
> JSON"——本文验证该判断，并调查 ifcopenshell 的 2D/DXF 能力到底做到哪一步。

## 1. ifcopenshell 的 2D 能力实况（本地源码 `AI_IFC/src/ifcopenshell-python` 实测）

| 模块 | 实际是什么 | 方向 |
|---|---|---|
| `ifcopenshell/draw.py`(743 行） | 2D 图纸生成器：从 IFC 模型出平面/剖面/立面图，序列化为 **SVG**；设置项含 auto_floorplan/space_names/door_arcs；内部用 **shapely** 做几何 | **IFC → 2D（反向）** |
| `ifcopenshell.geom` | 几何内核包装（含 arrange_polygon 等 2D 工具） | 通用 |
| DXF 相关 | **不存在**。全包无 `dxf` 模块，grep 仅命中 schema 文件与无关命名 | — |

结论：**"ifcopenshell 有 DXF 求解器"不成立**。它的 2D 能力是"从 IFC 生成图纸"
（出图方向），不是"从 DXF 理解出 IFC 构件"（识图方向）。后者（DXF→墙/门/空间
语义）在社区里本来就是空白地带——所以"DXF 融入 ifcopenshell 自动化"这条路
**不存在现成轮子，选了 DXF 就得自己写识图解析器**。

## 2. V2 有没有直接对标本需求的产物？——有，而且是设计时就埋好的

V2 产物链里**三个 JSON 全是"标记+空间坐标"形态**，DXF 反而是信息最贫瘠的一个：

| 产物 | 内容 | 对 bim 的用途 |
|---|---|---|
| **layout 矢量化输出**(P3.4,layout 包） | 房间直角多边形（带房间类型）/墙段（带两侧房间、长度）/门位（带 via 类型、所在墙）——**纯 shapely 几何 + 语义标签，刻意零 ezdxf 依赖** | IfcWall（墙段+墙厚拉伸）、IfcSpace（房间多边形+层高拉伸）、IfcDoor（门位）的直接数据源 |
| **building.json v2** | floors(elevation/height/sha256)+ **doors[] 门表** + metadata（材质/occupancy) | IfcBuildingStorey 层级与标高；IfcDoor 清单；Pset 属性来源 |
| **cad_draft.json bubble_graph** | 房间类型/邻接/连通的设计意图 | IfcSpace 功能分类、IfcZone 聚合、邻接关系语义 |

关键架构事实：layout 包设计时就规定"**算几何的不知道图纸**"（不 import
ezdxf)——这个当时为可测试性做的决定，现在证明正是 bim 衔接的准备：
**矢量化输出在进 archdxf 之前就存在，bim 消费它和 DXF 生成互不干扰**。

## 3. 三条候选路线的衡量

| 路线 | 优点 | 致命伤 | 判定 |
|---|---|---|---|
| A. bim 消费 DXF | DXF 反正要产出 | ①ifcopenshell 无 DXF 识图器，须自写；②DXF 语义靠图层约定，**信息有损**——门表、房间类型、竖向标高根本不在 DXF 里，反解=重新发明对账器 | ❌ |
| B. bim 消费 V2 的 JSON（矢量化输出+building.json) | 语义+坐标同源无损；shapely 几何与 ifcopenshell.draw 同 substrate，互操作顺滑；对齐架构文档 §4.3.6"脚本式转换→设计参数参考→ifcopenshell.api 建模" | 需要 layout 输出落盘成正式 JSON 契约（现在是包内数据结构） | ✅ **采用** |
| C. DXF+JSON 双消费 | 冗余校验 | 两套解析路径，成本翻倍无收益 | ❌ |

## 4. 落地动作（对 implement.md 的增补）

1. **新增 P3.8：layout 输出落盘契约** `layout_output.schema.json`——
   房间多边形（带 type)/墙段（带两侧房间与厚度建议）/门表/预锁定标记，
   每层一个 `<floor>.layout.json`，与 DXF 同目录交付。building.json 的
   floors[] 增加 `layout` 相对路径字段 + sha256。
2. **bim 转换器归属**：`cad.layout.json → ifcopenshell.api 建模脚本`是
   aiifc skill 适配化改造（架构文档 §4.3.6）的输入契约，V2 只负责把
   layout.json 做稳定（schema + canon 级确定性）。
3. **反向验证彩蛋**：bim 产出 IFC 后，可用 `ifcopenshell.draw`（出 SVG
   平面图）与 cad DXF 做图纸级回归比对——draw.py 此刻才进入我们的链路，
   方向是 IFC→图，不是 DXF→IFC。
4. `implement.md` P4.2 之后插入 P3.8；`architecture.md` S4 交付物清单
   增加 layout.json。

## 5. 一句话结论

**V2 的 bim 数据源 = layout.json（语义+坐标）+ building.json（竖向+门表）;
DXF 是给人和前端看的工程产物，不是 bim 的输入。ifcopenshell 没有 DXF 求解器，
它的 draw.py 是反向（IFC→SVG）出图器，可在 bim 之后做图纸级回归验证。**

## 6. 已执行的全盘对齐（2026-08-06)

主线/支线对调已回写各文档：

- `README.md` 架构图：layout.json 升事实源，DXF 降为 archdxf 渲染支线
- `architecture.md`:S3 流程重排（③-4 layout.json 落盘为 Gateway，渲染支线
  ③-5/工程对账 ③-6),S4 双轨交付表，§5 实现落点
- `01_layout_solver.md` §2：矢量化第 5 步=layout.json 落盘，第 6 步=DXF 渲染支线
- `03_reconciliation.md`：三路对账重构为**两层**（A 设计：气泡图↔layout.json
  纯 JSON 比对；B 工程：layout.json↔DXF 经 from_dxf)
- `implement.md`:P3.5/3.6/3.7 重排为 A 层/类型/B 层，P3.8 落盘契约、P3.9 双轨
  金样回归，P4.2 明确渲染器零独立逻辑

## 7. 人工编辑 DXF 后的同步桥（2026-08-06 增补）

问题：平台支持人手编辑 DXF → 交付后 layout.json 可能过期。
结论：**bim 仍只消费 layout.json，但它从"静态事实源"变为"可由 DXF 再生的
派生物"**;ifc 侧不平行造第二个解析器（双实现必漂移），复用 cad 侧
`layout.from_dxf`（一处投入三处受益：模板反编译 / B 层工程对账 / 本同步桥）。

bim 启动时的同步协议：

1. 重算 DXF sha256，与 building.json 记录比对：
   - 未变 → 直接消费交付时 layout.json（快速路径）;
   - 已变 → 进入再生流程。
2. 再生：`layout.from_dxf(编辑后 DXF)` → 新 layout.json。
3. 审计：新旧 layout.json diff → 人改了什么（墙位移/门增删/房间改名）。
4. 重跑 A 层设计对账：编辑是否破坏拓扑规则（断连通/穿套/面积出界）:
   - 0 FAIL → bim 消费再生 layout.json，building.json 哈希刷新；
   - 有 FAIL → 报告用户，人工裁决（改图或显式豁免，豁免记录进 metadata)。

语义保持边界（平台编辑器纪律，from_dxf 可无损再生的前提）:

- 编辑不越出 archdxf 图层约定（A-WALL/A-DOOR/A-GLAZ/A-ANNO):移动/增删
  标准构件 → 可解析；
- 平台编辑器应使用 archdxf 组件库作为编辑工具（改门=改 A-DOOR 实体）,
  而非自由画线——v1 对模型的纪律，主体换人后不变；
- 出现不可解析实体（自造图层/手绘线）:from_dxf **报"不可解析实体"并定位
  坐标**，不静默丢弃。
