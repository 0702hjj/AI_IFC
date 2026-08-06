# W-0005: 仓库卫生（Issue/PR 模板、CONTRIBUTING、示例模型）

- **状态：** in-progress
- **优先级：** P2
- **Milestone：** M3（见 PLAN-v0.1.0.md）
- **来源：** PLAN-v0.1.0（M3 发布化）+ roadmap 近期项
- **执行者/分支：** opencode / feat/m3-release

## 背景

v0.1.0 开源发布前的基础卫生：仓库无 Issue/PR 模板；CONTRIBUTING 只有 site 页面（docs/site/project/contributing.md），根目录缺 CONTRIBUTING.md 入口；示例模型只有 converter fixture，缺「拿来即玩」的示例。

## 涉及位置

- 新增：`.github/ISSUE_TEMPLATE/`（bug + feature 两个 yml 模板）、`.github/PULL_REQUEST_TEMPLATE.md`
- 新增/完善：根 `CONTRIBUTING.md`（指向 AGENTS.md + site 贡献页，避免内容重复漂移）
- `examples/` 或 `docs/site/public/`：示例 IFC 模型（buildingSMART 样例，注意许可证标注）

## 方案

- Issue 模板：bug（环境/复现/期望/日志）与 feature（场景/提案/替代方案）两个 form
- PR 模板：勾选清单（测试、docs check:api、工作项关联）——与 AGENTS.md 的契约一致，关联 docs/work/ 工作项 ID 栏位
- CONTRIBUTING.md 根入口：30 行内，链 AGENTS.md（命令/纪律）+ site 贡献页（流程），单一事实来源不复制
- 示例模型：用 research/ 里 buildingSMART Sample-Test-Files 的样例（wall-with-opening-and-window 已用作 fixture），README 说明来源与许可证

## 验收标准

- gh 新建 issue/PR 时模板生效（merge 后 GitHub 上可见）
- CONTRIBUTING.md 链接全部可达
- 示例模型可被平台正常上传转换（smoke 验证）

## 测试要求

- 模板 yml 语法校验
- docs:build 不受影响；若动 site 页面需 check:api 通过
