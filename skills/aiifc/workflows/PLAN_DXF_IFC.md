# Plan → Script → IFC 工作流（辅助设计师，script-as-source）

> 本文是 aiifc skill 的**可选工作流编排层**：规定「可选 plan 草稿 → 构建脚本（事实源）→ IFC」的阶段顺序。
> 与 `SKILL.md` 的关系：`SKILL.md` 讲「怎么建 IFC」（建模纪律 + 脚本契约 MUST #25-31），本文讲「一次任务走哪几步、每步产什么」。
> **选择性地使用**：适用于「从想法到 IFC」的辅助设计师场景；简单的直接建模（单墙/板）或用户已明确指向某阶段的输入，**不必走完整流程**。

## 定位

辅助**设计师**开发：AI 生成构建脚本，设计师在 PARAMS 表单 / 脚本上确认修改，脚本运行产出 IFC。
**Python 构建脚本是 IFC 的唯一一一对应表示（事实源）**；design JSON / DXF 均为辅助信息——不是完整表示、不进版本、不做 diff。

## 阶段总览

```
① plan（可选草稿）  design.json / plan.dxf  设计意图（纯语义：墙轴/洞口沿轴/层高，无坐标）
   │                                      由 LLM 依用户需求产出，供用户确认平面；
   │                                      标注：辅助信息，非完整表示，非事实源
   ▼
② script            scripts/v{n}.py        唯一事实源：完整构建脚本
   │                                      符合脚本契约（SKILL.md MUST #25-31）：
   │                                      PARAMS 块 + 确定性 GlobalId + build() 入口 + validate 出口
   ▼
③ ifc               versions/v{n}.ifc      派生物：脚本运行的产物
```

## 每阶段的 MUST

### ① plan（可选草稿）

- 复杂平面/异形/多层时，可先产 design JSON 草稿框定意图（读 `references/DESIGN_JSON_SCHEMA.md` 和 `references/SPATIAL_QUALITY.md` 再产出）。
- plan = **辅助信息**：只帮助用户确认意图，**绝不计算坐标**，不是 IFC 的完整表示，不进版本、不做 diff。
- 可选地用 `dxf_from_design.py` 出 2D 平面图供确认：
  ```bash
  <your-python> <skill_root>/references/docs/flows/dxf_from_design.py design.json -o plan.dxf
  ```
- 完成标准：用户确认 plan（或明确跳过）后进入 ②；草稿本身不承担任何契约。

### ② script（事实源）

- 产出**完整构建脚本** `scripts/v{n}.py`（无系统编排时写当前目录 `model.py`），必须符合脚本契约（`SKILL.md` MUST #25-31）：
  - 顶层 `PARAMS = {...}` 字面量 dict（JSON-compatible），所有可调参数集中于此；
  - 构件 GlobalId 用 `script_lib.deterministic_guid(key)`，key 稳定唯一 `{storey}:{kind}:{n}`，写 `Pset_AIIFC.designKey`；
  - 入口 `build(params, out_path)`，`__main__` 用 PARAMS 调 build；
  - 出口 `script_lib.write_and_validate`。
- 由 design JSON 草稿出发时，可经 `design_builder.py` → features.json → `build_script_template.py` 生成首个脚本；此后**脚本是唯一编辑面**，草稿即弃。
- 完成标准：`script_lib.validate_script_contract(path)` 通过（无错误项）。

### ③ ifc（派生物）

- 运行脚本生成 `versions/v{n}.ifc`（无系统编排时写 `model.ifc` 或系统约定的 `uploads/{modelId}.ifc`）。
- 完成标准：`ifcopenshell.validate` 通过 + `design_review.py` 无 ERROR。
- IFC 是派生物：**从不直接手改 IFC 当作修改**——改模型一律回到 ② 改脚本重跑。

## 改模型 = 改脚本（唯一答案）

| 用户输入 | 走哪几步 |
|---|---|
| 「建一栋两层小楼」 | ①→②→③（完整流程，①用于用户确认平面） |
| 「把外墙改厚到 300」 | ②→③：**增量编辑既有脚本**（PARAMS 里改 `wall_t`）→ 重跑 |
| 「改这面墙位置」 | ②→③：增量编辑脚本中该墙的轴段/参数 → 重跑 |
| 「先看看平面图」 | ①（到 DXF 为止，不生成脚本/IFC） |
| 「上传一个 IFC 让我看」 | 只渲染，不生成 |

> **增量纪律（MUST #28）**：修改既有模型 = 增量编辑既有脚本，**禁止重写**。AI 下次介入的输入是「当前脚本 + 脚本 diff + IFC 语义 diff 摘要」，重写会毁掉 diff 可读性。

## 版本模型与 diff（三层）

- 每次**确认保存**（大版本）成对快照：`scripts/v{n}.py`（事实源）+ `versions/v{n}.ifc`（派生物）。
- 回退 = 恢复 `scripts/v{n}.py` → 重跑 → IFC。
- staging（5-10 步短回溯链）：每步 = 脚本一次修改的快照；保存 → 大版本。

| diff 层 | 对象 | 受众 |
|---|---|---|
| 脚本 unified text diff | scripts/v{n-1}.py ↔ v{n}.py | AI（下次输出的上下文） |
| IFC 语义 diff（ifcdiff，属性级 GlobalId 对齐） | versions/v{n-1}.ifc ↔ v{n}.ifc | 用户（Diff Viewer） |

- IFC 语义 diff 的跨版本对齐依赖 ② 写入的确定性 GlobalId 与 `Pset_AIIFC.designKey`。

## 相关

- `SKILL.md` MUST #25-31 — 脚本契约（PARAMS / 确定性身份 / build 入口 / 增量纪律 / validate 出口）
- `references/docs/flows/script_lib.py` — 契约实现层（deterministic_guid / attach_design_key / create_skeleton / write_and_validate / validate_script_contract）
- `references/DESIGN_JSON_SCHEMA.md` — design JSON 草稿格式（可选，辅助信息）
- `references/docs/flows/dxf_from_design.py` — plan 草稿 → DXF
- `references/docs/flows/design_builder.py` — design JSON → features.json
- `references/docs/flows/build_script_template.py` — features.json → IFC（script_lib 薄封装）
