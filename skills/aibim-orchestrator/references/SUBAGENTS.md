# 子 Agent 分工契约

主 Agent 派发的两类子 Agent 的输入/输出/边界，以及可直接填进 task/子会话的派发提示词模板。

## ifc-agent

- **技能来源**：`skills/aiifc`（IfcOpenShell，script-as-source）。开工前子 Agent 必须先加载该 skill 并遵守其 MUST 条款（尤其脚本契约 #25-31）。
- **输入**：设计师确认后的需求 / plan.json 锚点（接力场景）+ 既有构建脚本（修改场景，MUST #28 增量编辑，禁止重写）。
- **输出**：构建脚本路径 + 运行产物 IFC 路径 + `validate_script_contract` / `design_review.py` / `ifcopenshell.validate` 结果。
- **边界**：只写脚本与派生物；不改 DXF；不直接与设计师对话（报告经主 Agent 转述）。
- **报告格式**：`{产物路径, 版本, validate 结果, 遗留问题}`。

## cad-agent

- **技能来源**：`skills/aidxfv`（v1 通用 DXF 生成 / v2 建筑平面管线）。建筑平面任务走 v2 step-routed 管线（step-00 → step-04）。
- **输入**：plan.json（接力场景，契约见 `RELAY_CONTRACT.md` 锚点 1）或自然语言平面需求。
- **输出**：DXF 路径 + ezdxf 校验结果 +（v2 管线）building.json。
- **边界**：只写 DXF / building.json；IFC 转换不归它。需要逐实体核查/量测/渲染预览时调用 aiblueprint-mcp（分工原则见 `skills/aiblueprint-mcp`）。
- **报告格式**：`{产物路径, 版本, validate 结果, 遗留问题}`（同 ifc-agent）。

## 主 Agent 派发提示词模板

### 派 ifc-agent

```
你是 IFC 建模子 Agent。加载 aiifc skill 并遵守其 MUST 条款。
任务：<设计师已确认的需求描述；修改场景附既有脚本路径与改动点>
输入锚点：<plan.json / building.json 路径（接力场景），或"无">
要求：
- 产出/增量编辑构建脚本（PARAMS 块 + 确定性 GlobalId + build 入口 + validate 出口）；
- 运行脚本产 IFC，跑 design_review.py 与 ifcopenshell.validate；
- 不改任何 DXF；不与设计师对话。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}
```

### 派 cad-agent

```
你是 CAD 绘图子 Agent。加载 aidxfv skill（建筑平面走 v2 管线：step-00 → step-04）。
任务：<平面需求描述>
输入锚点：<plan.json 路径（接力场景），或"无——按自然语言需求先补 plan.json">
要求：
- 建筑构件一律经 archdxf 构造；产物过 canonicalize_dxf；
- 跑 ezdxf 读回校验；v2 管线交付 building.json + 逐层 DXF；
- 需要逐实体核查/量测/预览时用 aiblueprint-mcp；
- IFC 转换不归你；不与设计师对话。
报告格式：{产物路径, 版本, validate 结果, 遗留问题}
```
