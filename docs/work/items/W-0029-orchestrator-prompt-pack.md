# W-0029: 主 Agent 编排提示词包（aibim-orchestrator）

- **状态：** done
- **关闭于：** 本迭代分支 feat/v0.5-portability-reuse（PR #31）
- **优先级：** P1
- **Milestone：** v0.5（可移植复用）
- **来源：** spec 2026-08-12-portability-reuse-design.md §4（统合 W-0017 + plan→cad→ifc 推荐路径）
- **执行者/分支：** opencode / feat/v0.5-portability-reuse

## 背景

W-0017 原方向是代码级 orchestrator；2026-08-12 用户裁决改为 **agent-agnostic 提示词包 + 数据契约**，不写代码级 orchestrator。设计师只与主 Agent 交互，主 Agent 派生子 Agent（类比 opencode task 工具），统合 W-0017 多 agent 协同与 plan→cad→ifc 推荐路径。

## 涉及位置

- `skills/aibim-orchestrator/`（新增，名称实施时定）
- `docs/work/items/W-0017-orchestrator-agent.md`（关闭，注明形态变更理由与本 spec 指针）
- `docs/superpowers/specs/2026-08-11-orchestrator-design.md`（补修订说明）
- `docs/superpowers/specs/2026-08-11-platform-framework-design.md` §5（同步修订：推荐项落地形态=提示词包）
- `tests/skill/`（真实 skill 校验/打包测试）

## 方案

交付物（放 `skills/aibim-orchestrator/`）：
1. **主 Agent system prompt**：意图路由规则——IFC 改图 → 派 aiifc 子 Agent；CAD 改图 → 派 aidxfv 子 Agent；全链路 → plan→cad→ifc 接力编排；含子 Agent 提示词模板。
2. **子 Agent 分工契约**：每个子 Agent 的输入/输出/边界（只读什么、只写什么、报告格式）。
3. **接力数据契约**：plan.json → DXF → IFC 的锚点格式（字段、单位、坐标约定、版本对应关系），复用 aidxfv v2 已有 plan.json 约定；给正/反 fixture 各一（plan.json 样例 + 校验说明）。
4. **opencode 配置示例**：`.opencode/agent/` 下的主/子 Agent 定义示例；其他 agent 运行时照契约移植。

连带处理：
- W-0017 关闭：形态由「代码 orchestrator」改为「提示词包」，item 注明变更理由与本 spec 指针。
- `2026-08-11-orchestrator-design.md` 补修订说明：Eino/代码编排方向退役为「不推荐」，事件总线（已交付）保留但提示词包不依赖它。
- 框架 spec §5 同步修订。

## 验收标准

- `skills/aibim-orchestrator/` 可被 `skill_pack.py --skill-dir` 正常打包（registry + frontmatter 契约测试通过）。
- 接力数据契约正/反 fixture 齐。
- W-0017 状态置 done（注明形态变更）。
- 两份 spec 修订落盘。

## 测试要求

- `tests/skill` 新增真实 skill 校验/打包测试（复用 frontmatter 校验契约）；新增测试量 ≥ 新增实现量。
