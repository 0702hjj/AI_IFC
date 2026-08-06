---
name: step-03-build
description: Generate per-floor DXF from the confirmed draft via the scaffold + archdxf pipeline, passing the validation gate.
---

# Step 3: 构建（逐层 DXF）

## 输入
- plan.json（`confirmed: true`，draft 为硬约束）
- `references/scaffold_floor_plan.py`
- `references/archdxf_api.md`、`references/vocabulary.md`
- `references/building_types/_template.md` + 类型包

## 执行（每层重复）
1. 复制 `references/scaffold_floor_plan.py` 为本层生成脚本，只改 DECLARATION
   段：轮廓、结构墙、隔墙、开洞、柱、楼梯、房间名——全部对齐 draft。
2. 规则加载顺序：**先 `_template.md` T0（全包继承），再类型包 T1-T8**。
   类型包只能收紧 T0，冲突以更严者为准；违反 T1 NOT FOR 必须停手。
3. 非脚手架覆盖的元素，按 `references/vocabulary.md` 用 `archdxf` 画法；
   词汇表没有的构件，用 `ezdxf` 自由绘制并归入正确图层。
4. 运行生成脚本。VALIDATION ZONE 输出任何 **FAIL → 必须修图重跑，不许解释过去**;
   WARN 逐条判断，豁免理由写入交付说明。
5. 自查（声明层为主）：走 `references/floor_plan_assembly.md` §3-4 清单——
   数量、门窗启闭方向、图层归属、文字样式统一、未连接元素、楼梯占位。
   数字判不清的歧义项才用 aiblueprint MCP 渲染辅助：
   `aiblueprint_drawing open` → `aiblueprint_view screenshot`。
6. `archdxf` canonicalize 本层 DXF，再跑一次生成比对确认确定性。

## 输出
- 每层一个 canonical DXF：`<输出目录>/<floor_name>.dxf`
- 每层生成脚本（与 DXF 同目录或指定位置，保证可复跑）

## 完成条件
所有层 DXF 通过验证（0 FAIL）、通过 canon 确定性比对，然后进 step4。
