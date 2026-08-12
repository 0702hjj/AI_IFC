# W-0032: cad_script_lib + 契约校验（DXF script-as-source 契约层）

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §1.1 + 「工作项建议」1 + 「测试要求」
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

DXF handle 由 CAD 软件分配、重存全变，不能当 GlobalId 用。spec 决策 2 锁定：稳定身份 = XDATA 确定性 key（APPID `AIDXF`，key = `uuid5` 风格确定性派生，格式 `{layer}:{kind}:{n}`）+ ScriptMap 侧车（key → 脚本行号/列/参数键）。本项交付该契约层：DXF 侧复刻 IFC `script_lib` 的 `cad_script_lib`，连同纯函数契约校验 `validate_script_contract()`，契约测试先行（TDD）。这是 chunk A 的第一块，services/cad（W-0033）与后续 locate/edit-call/语义 diff 全部建立在其上。

## 涉及位置

- `skills/aidxfv/v1/`（新增 flows 目录契约层：`cad_script_lib` 唯一实现；复刻 aiifc flows 分工——skill flows 为唯一实现，services/cad 经环境变量路径 import，同 `AIIFC_FLOWS_DIR` 机制）
- `skills/aidxfv/v1/SKILL.md`（新增 DXF 脚本契约节，复刻 aiifc 契约 #25–31）
- `skills/aidxfv/v1/tests/` 或对应 skill 测试目录（契约测试）
- `tests/skill/`（registry/打包测试扩展，若需）

## 方案

1. **`cad_script_lib`（skill flows 目录）**：
   - `add_entity(kind, **kwargs)` 实体工厂：七类实体 LINE / LWPOLYLINE（含 bulge）/ CIRCLE / ARC / TEXT / MTEXT / INSERT；工厂分配确定性 key（uuid5 风格，格式 `{layer}:{kind}:{n}`），写 XDATA（APPID `AIDXF`），记录 callsite。
   - `write_and_validate(doc, out_path)`：ezdxf audit/recover 校验 + 写 ScriptMap 侧车 `out.dxf.map.json`（`{key: {line, col, snippet, origin, params_keys}}`，envelope 带 `scriptHash`，与 IFC 侧 `script_runner.py` 同形）；落裸 map（无侧车包装）。
   - 脚本契约：头部 `PARAMS = {...}` 顶层字面量 dict（JSON-compatible）；入口 `build(params, out_path)` + `__main__`；只允许工厂创建实体（C-locate）；web 可编辑参数为标量字面量或 PARAMS 引用（C-scalar）；增量编辑不重写整个脚本。
2. **`validate_script_contract()`**：纯函数校验器（返回错误列表，与执行分离），检查上述契约条目，正反例齐全。
3. **aidxfv v1 SKILL.md 契约节**：把契约写成 skill MUST 级纪律，镜像 aiifc 契约条款编号风格。

## 验收标准

- `validate_script_contract` 正反例测试绿（每个契约条目有正例 + 至少一个反例）。
- XDATA key 确定性测试绿：同脚本跑两次，产出 key 完全相同。
- `add_entity` 七类实体工厂（LINE/LWPOLYLINE/CIRCLE/ARC/TEXT/MTEXT/INSERT）均产带 XDATA key 的实体。
- `write_and_validate` 落裸 map（`out.dxf.map.json`，envelope 带 `scriptHash`）。
- aidxfv v1 SKILL.md 契约节落盘；`python -m pytest tests/skill/ -q`（registry/打包测试）绿。

## 测试要求

- 契约测试先行（TDD）：先写失败测试再实现。
- 覆盖：`validate_script_contract()` 正反例；XDATA key 确定性（同脚本两跑 key 全同）；七类工厂实体 key/XDATA 断言；write_and_validate 侧车 schema（含 `scriptHash`）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
