---
name: aiblueprint-mcp
description: Drive the aiblueprint MCP server for interactive DXF inspection, editing, measuring, and preview. Use when working with aiblueprint_* MCP tools (drawing/entity/layer/block/annotation/view/project/compliance), opening existing DXF files, measuring areas/perimeters, moving/offsetting/filleting entities, undo/redo, rendering screenshots or previews, running the jurisdiction questionnaire, or generating compliance-checked site plans. NOT for batch DXF generation from Python sources (use aidxfv1 for that).
metadata:
  project: AI_CAD
  upstream: thebossnow/aiblueprint-mcp (MIT)
---

# AIBlueprint MCP 交互式 DXF 操作

## 分工原则（先判断用哪条链路）

| 任务 | 用 |
|---|---|
| 批量生成整张 DXF(plan→cad 管线、参数化重生成、落盘交付） | **aidxfv1** skill(cadpy CLI,`gen_dxf()` 契约） |
| 打开已有 DXF 逐实体核查、量测、微调、人审改图、截图自查 | **本 skill**(aiblueprint MCP 工具） |

MCP 工具逐实体调用，token 成本高，**不要用它从零画整图**；它的价值在交互与监察。

## 工具地图（8 工具）

- `drawing`:create / open / info / save / list / switch / **undo / redo**
- `entity`：建（create_line/circle/polyline/rectangle/arc/text/mtext/hatch、import_boundary)；查（list / get / **measure**)；改（copy / move / rotate / scale / mirror / offset / array / fillet / erase)
- `layer`:list / create / set_current / set_properties / freeze / thaw / lock / unlock
- `block`:list / insert / insert_with_attributes / get_attributes / update_attribute / define
- `annotation`:create_text、create_dimension_linear/aligned/angular/radius(dim_overrides 支持 dimtxt/dimasz/dimlunit/dimclrd/dimclre/dimclrt/dimtxsty)、create_leader
- `view`:**screenshot**(matplotlib,PNG 直接可见）/ preview（需 LibreCAD)/ export(PNG/PDF/SVG/GeoJSON)
- `project`:start / question / answer / profile / status / reset / counties / cities / **generate_site_plan**
- `compliance`：面积/退让/覆盖率/限高检查，带法条引用（仅加州数据）

## 标准工作流程

**A. 产物核查/微调（最常用）**:
1. 目标 DXF 若在 workspace 外，先 `cp` 进 `AIBLUEPRINT_WORKSPACE`（沙箱限制，绝对路径/`..` 会被拒）
2. `drawing.open` → `entity.list`（可按 layer 过滤）→ `entity.measure` 量测
3. 修改后 **`view.screenshot` 自查**，确认无误再 `drawing.save`；改错用 `drawing.undo` 回滚
4. 注意：MCP 直接改 DXF 后，cadpy 产物与源码脱钩（sourceHash 可检出）——重大修改应回到 aidxfv1 改 `gen_dxf()` 源码重生成，MCP 只做微调

**B. 问卷→法规→一键 site plan**:
`project.start` → 逐问 `answer`(HOA=no 会跳过追问）→ `profile`（分层取最严+法条引用）→ `generate_site_plan(lot_width, lot_depth, adu_width, adu_depth)`

**C. 手动建图**:`drawing.create` → `layer.create` → `entity.create_*` → `annotation.create_dimension_*` → screenshot 循环 → save/export

## 关键 Gotchas（犯错高发区）

1. **offset 方向**：正值=外扩（CCW 走向）；顺时针矩形须用**负值**内缩——先小值试
2. **fillet**：两线须共端点；方向从交点向远端点取
3. **实心填充**:hatch 用 solid fill 语义，没有 "SOLID" 这个 pattern 名
4. **标注覆盖**：走 dim_overrides 参数，不要试图直接改 dim 实体属性
5. **undo 粒度**：每个修改操作一个 checkpoint；连续修改 undo 需逐次回退
6. **预览**:preview 依赖 `AIBLUEPRINT_LIBRECAD_BIN`，未配置时用 screenshot(matplotlib）即可，不算失败

## 已知边界

- 无建筑语义工具（墙/门/窗级命令）——实体级操作，建筑规范在 aidxfv1 侧
- 法规数据仅加州；不规则地块可 import_boundary + compliance 检查，但 generate_site_plan 只支持矩形地块

## 完整手册

详见 `skills/aiblueprint-mcp/README.md`（工具全表、Gotchas 原理、P0-P7 测试方案、实测记录）。
