# W-0053: cad 编辑两套依赖（dxfkit + archdxf）合并评估——跑通后的合适性审查

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.13（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-21 用户裁决：「当前 cad 编辑，人机走的是我合并的两套依赖（dxfkit + archdxf），虽然跑通了但后续需要注意合不合适」
- **执行者/分支：** （领取时填）

## 背景

cad 编辑（人机共用）现在走的是合并的两套依赖：

- **dxfkit**（`skills/dist/aidxf/scripts/packages/dxfkit/src/dxfkit/`）：draw（画法工具箱，主 agent 逐构件调用）、readback（读 DXF→房间图/门窗）、record（调用序列→固化 build 脚本）、svg（预览）。
- **archdxf**（`skills/dist/aidxf/scripts/packages/archdxf/src/archdxf/`）：frames（墙框）、annotate（标注）、openings（门窗）、canon（规整化）、stairs、layers、fixtures、intervals。

关系：**dxfkit.draw 是 archdxf 的画法封装**（`from archdxf import annotate, fixtures, frames, layers, openings, stairs`）；dxfkit.readback 读 DXF、record 把 draw 调用序列固化为「archdxf 环境可运行的 build() 脚本」。

三条消费路径同源合并：
1. AI 生成（aidxfv3 CLI `import dxfkit.draw/readback/svg`）；
2. 人机编辑（services/cad `sandbox_exec` 注入 PYTHONPATH = flows + drawlib_dir（archdxf + dxfkit src））；
3. cad→ifc 消化（aiifc consume_upstream `from dxfkit.readback import readback`，editable 装进 skills/.venv）。

**现状：功能跑通了**（端到端验证过），但「两套包合并」的合适性没有正式评估：

- 两套包源文件都在 skill dist 内（打包器 skill_pack.py 打不打包？分开的 egg-info 是否漂移？）；
- dxfkit.draw 薄封装 archdxf——分层边界是否清晰，还是复制了 archdxf 的几何逻辑；
- editable 安装（dxfkit 进 skills/.venv）与 skill dist 打包的同步风险（已踩过一次：venv 旧 editable → dist 未同步 → `unrecognized`）；
- services/cad 人机编辑路径与 aidxfv3 AI 路径同源——改动 dxfkit 会不会双路径漂移。

## 涉及位置

- `skills/dist/aidxf/scripts/packages/dxfkit/`（draw / readback / record / svg）
- `skills/dist/aidxf/scripts/packages/archdxf/`（frames / annotate / openings / canon / stairs / layers / fixtures / intervals）
- `services/cad/app/config.py`（drawlib_dir 推导 + 注入）· `sandbox_exec.py`（PYTHONPATH）
- `skills/aiifc/scripts/aiifc_cli/aiifc/cli.py`（consume_upstream 的 dxfkit.readback 引用）
- `tools/install_skill_venv.sh` / `tools/skill_pack.py`（editable 安装 + 打包）

## 方案

1. **合并边界评估**：理清 dxfkit 与 archdxf 的分层契约（draw 封装了什么、readback 是否反依赖 archdxf、record 固化到哪套环境）。产出一页「两套依赖关系 + 职责边界」文档。
2. **打包/安装一致性**：验证 skill_pack.py 对 packages/ 的打包行为 + install_skill_venv.sh 的 editable 安装同步机制——保证 venv 与 dist 一致（防 `unrecognized` 类问题重演）。
3. **合适性决策**：评估三种方向并给建议——① 维持现状（两包并存，记录边界）② 合并为单一 dxfkit 包（archdxf 收编进 dxfkit）③ 明确上游化（archdxf 作为独立依赖，dxfkit 只封装）。决策记录进 item。
4. **双路径漂移防护**：services/cad 人机编辑与 aidxfv3 AI 路径同源——补一条测试/检查保证改 dxfkit 不破另一条路径。

## 验收标准

- 「两套依赖关系 + 职责边界」文档产出（落 docs/internal/ 或 skill 内 README）。
- 打包/安装一致性验证通过（venv 与 dist 同步机制可复现）。
- 合并方向有明确决策（维持/合并/上游化之一 + 理由），决策记录在 item。
- 双路径回归：AI 生成（aidxfv3 CLI 跑通）+ 人机编辑（services/cad sandbox 跑通）+ cad→ifc 消化（consume_upstream 跑通）三条路径在决策后保持绿。

## 测试要求

- 若方向 ②/③ 涉及代码移动：对应包的行为测试全绿（现有 aidxfv3 / services/cad / aiifc 测试不破）。
- 新增/更新 1 条「venv 与 dist 一致性」检查（防旧 editable 漂移）。
- 测试量 ≥ 实现量。
