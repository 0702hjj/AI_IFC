# v0.5 可移植复用设计：契约文档化 + skill 分发 + 主 Agent 提示词包

> 日期：2026-08-12 · 状态：待用户审批
> 前置：2026-08-11-platform-framework-design.md（两个对等逻辑 + 可复用性原则）、W-0017、v0.1~v0.4 已收口
> 用户裁决记录（2026-08-12 会话）：主目标=单组件可独立分发（先）+ services/cad（后，完全同构 ifc）；core 可移植=契约文档化（轻）；前端=文档即可不动 web；skill=Release + 版本化；plan→cad→ifc 与 W-0017 统合=提示词包 + 数据契约；fork 复用文档=VitePress 已够，本轮不做。

## 1. 定位与范围

本轮把框架 spec 的「可复用性优先」从结构落地推进到**对外可消费**：第三方能拿着契约文档对接存储/前端，能下载安装 skill，能按提示词包搭起 plan→cad→ifc 的主/子 Agent 编排。

**本轮做**：①契约文档化 ②skill 版本化 + Release 分发 ③主 Agent 编排提示词包（统合 W-0017 与推荐路径）。
**本轮不做**：services/cad 实施（仅锁方向）；web 主题化；代码级 orchestrator；fork 复用指南（已有）。

## 2. ① 契约文档化（core 可移植，轻量）

新增公开站文档集《平台对接契约》（`docs/site/`，中英文按站点惯例）：

1. **存储接口契约**
   - Go `server` store 抽象：文件存储（默认零依赖）/ PG（可选）的接口面与切换方式。
   - `VIEWER_DATA_DIR` 数据目录布局（models / scripts / versions / maps 等），edit-service 与 server 共享约束。
   - PG schema 说明：第三方「整合进已有数据库」的两条路径——实现 store 接口，或直接复用本仓 PG schema。
2. **前端对接契约**
   - 基于 Go OpenAPI（`docs/site/public/go-rest-api.routes.json` 已有生成物）说明自研/第三方前端如何对接：envelope `{code,message,data}`、SSE 事件、script-as-source 编辑流程（PUT /script → run → save → locate）。
   - 明确 `web/` 是参考实现，可整体替换；不改 web 代码。
3. **services/ifc 独立部署**
   - 补 `services/ifc/Dockerfile`：单容器可跑（uv + ifcopenshell，`VIEWER_DATA_DIR` 挂载），脱离本仓骨架独立部署。
   - 配套文档更新现有独立部署指南。

验收：文档入站并通过 `npm run docs:build`；Dockerfile 实际构建并冒烟（起容器 → 上传/编辑一条链路通）。

## 3. ② skill 版本化 + Release 分发

- 三个 skill（`skills/aiifc`、`skills/aidxfv`（v1/v2）、`skills/aiblueprint-mcp`）frontmatter 补 `version` 字段，各自加 CHANGELOG（从本次版本起记）。
- `tools/skill_pack.py`：archive 产物命名带版本号（读 frontmatter），缺 `version` 报错。
- 发布流程：打 tag 后按文档化手工流程（`gh release create` 挂打包产物）发布；CI 自动化本轮不做，后置可选。
- 新增《skill 获取与安装》文档：Release 下载 → 解压到 `~/.agents/skills/`（及各 agent 运行时等价目录）→ 即用。

验收/测试：打包命名与 frontmatter 校验入 `tests/skill/` 契约测试；Release 流程至少走通一次（可预发 tag 验证）。

## 4. ③ 主 Agent 编排提示词包（统合 W-0017 + plan→cad→ifc）

形态：**agent-agnostic 提示词包 + 数据契约**，不写代码级 orchestrator。设计师只与主 Agent 交互，主 Agent 派生子 Agent（类比 opencode task 工具）。

交付物（放 `skills/` 下新目录，如 `skills/aibim-orchestrator/`，名称实施时定）：

1. **主 Agent system prompt**：意图路由规则——IFC 改图 → 派 aiifc 子 Agent；CAD 改图 → 派 aidxfv 子 Agent；全链路 → plan→cad→ifc 接力编排；含子 Agent 提示词模板。
2. **子 Agent 分工契约**：每个子 Agent 的输入/输出/边界（只读什么、只写什么、报告格式）。
3. **接力数据契约**：plan.json → DXF → IFC 的锚点格式（字段、单位、坐标约定、版本对应关系），复用 aidxfv v2 已有 plan.json 约定。
4. **opencode 配置示例**：`.opencode/agent/` 下的主/子 Agent 定义示例；其他 agent 运行时照契约移植。

连带处理：
- W-0017 关闭：形态由「代码 orchestrator」改为「提示词包」，item 注明变更理由与本 spec 指针。
- `2026-08-11-orchestrator-design.md` 补修订说明：Eino/代码编排方向退役为「不推荐」，事件总线（已交付）保留但提示词包不依赖它。
- 框架 spec（2026-08-11-platform-framework-design.md）§5 同步修订：推荐项落地形态=提示词包。

验收/测试：提示词包目录能被 `skill_pack.py --skill-dir` 正常打包（复用 frontmatter 校验契约测试）；接力数据契约给正/反 fixture 各一（plan.json 样例 + 校验说明）。

## 5. ④ services/cad 方向锁定（本轮不实施）

- 目标（下一迭代入口）：与 `services/ifc` 完全同构——DXF 生成脚本为唯一事实源（script-as-source）、版本快照、实体级语义 diff、同一套 REST 编辑 API 形状（PUT /script → run → save → locate）。
- 本轮仅把方向写入 PLAN 与新工作项（open），不动代码。

## 6. 工作项与 milestone 建议

新增工作项（ID 按 W-0026 起递增，状态 open）：

| ID | 内容 | 对应块 |
|---|---|---|
| W-0026 | 存储接口契约 + 前端对接契约文档 | ① |
| W-0027 | services/ifc Dockerfile + 独立部署冒烟 | ① |
| W-0028 | skill 版本化 + skill_pack 命名 + Release 分发 + 安装文档 | ② |
| W-0029 | 主 Agent 提示词包 + 接力数据契约 + W-0017 关闭/spec 修订 | ③ |
| W-0030 | services/cad 同构方向立项（仅方向文档，下迭代实施） | ④ |

PLAN-v0.1.0.md 增 v0.5 milestone 行：完成判据=契约文档入站、Dockerfile 冒烟通过、skill Release 走通一次、提示词包可打包且契约 fixture 齐。

## 7. 纪律与边界

- PR 节奏不变：同一迭代分支累积，收工一次提；CI 绿后合并。
- 测试纪律：skill_pack 命名/frontmatter 校验、提示词包打包契约须配测试（≥1:1）；纯文档块除外。
- 边界不动：`skills/aidxfv/v1` 与 `skills/aiblueprint-mcp` 的 MIT 归属（各自 LICENSE 保留）；`docs/internal`/`docs/work`/`docs/superpowers` 内容不进公开站；`docs/site/public` 生成物只经 `npm run gen:api` 更新。
