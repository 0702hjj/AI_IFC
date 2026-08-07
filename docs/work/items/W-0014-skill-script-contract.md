# W-0014: skill 契约更新（PARAMS + 确定性身份 + 脚本工作流）

- **状态：** done
- **关闭于：** b1f5c54 + be07a45
- **优先级：** P0
- **Milestone：** M5 script-as-source（见 spec 2026-08-06-script-as-source-design.md）
- **来源：** spec §脚本契约
- **执行者/分支：** opencode / feat/script-as-source

## 背景

script-as-source 转向后，AI 生成的构建脚本是 IFC 唯一事实源。skill 必须规定脚本契约，否则表单 UI、确定性 diff、增量修改纪律都无从谈起。本项是所有其他 M5 项的前置（定义契约）。

## 涉及位置

- `skills/aiifc/SKILL.md`（MUST 清单增补）
- `skills/aiifc/workflows/PLAN_DXF_IFC.md`（重写：design JSON 降级为可选草稿）
- `skills/aiifc/references/docs/flows/`（新增/改造公共 helper）
- `skills/aiifc/references/MODELING_WORKFLOWS.md`（Parametric path 与新契约对齐——当前与 PLAN_DXF_IFC 矛盾）

## 方案

1. **flows 新增 `script_lib.py`**（或扩展既有公共模块）：抽出现 build_script_template.py 的确定性机制为可 import 的 helper——`NAMESPACE_AI_IFC`、`deterministic_guid(key)`、`attach_design_key(model, entity, key)`、skeleton 创建、validate 出口。build_script_template.py 改为薄封装调用 helper（保持现有测试绿）
2. **SKILL.md MUST 新增**：
   - 脚本必须含 `PARAMS = {...}` 顶层字面量 dict（JSON-compatible，所有可调参数集中于此）
   - 构件 GlobalId 必须 `deterministic_guid(key)`，key 稳定唯一 `{storey}:{kind}:{n}`，写 Pset_AIIFC.designKey
   - 脚本入口 `build(params, out_path)`；`__main__` 用 PARAMS 调 build
   - 修改既有模型 = **增量编辑既有脚本**（禁止重写），保存 diff 可读性
   - 产物必须过 ifcopenshell.validate
3. **PLAN_DXF_IFC.md 重写**：工作流改为 plan（可选 design JSON 草稿，标注「辅助信息，非完整表示」）→ script（事实源）→ IFC；版本模型 scripts/v{n}.py + versions/v{n}.ifc；diff = 脚本 diff（AI）+ IFC 语义 diff（用户）
4. **MODELING_WORKFLOWS.md** 的 Parametric path 段与新契约统一（消除「改 JSON 还是改 script」的矛盾）

## 验收标准

- skill 打包测试 42 全绿；`python tools/skill_pack_aiifc.py --archive` 通过
- helper 被 build_script_template 使用且 CI flows 冒烟（skeleton/full_building）不回归
- 三份文档对「改模型改什么」只有一个答案：改脚本（PARAMS 为表单入口）

## 测试要求

- `tests/skill/` 新增：helper 的确定性 GlobalId（同 key 两次一致）、PARAMS 契约校验函数（如提供 `validate_script_contract(path)` 检查 PARAMS 存在且 JSON-compatible）的用例
- 文档与代码漂移防护：参照 test_design_schema_example.py 的模式
