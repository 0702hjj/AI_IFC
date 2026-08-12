# W-0030: services/cad 同构方向立项

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.5（可移植复用，本轮仅立项不实施）
- **来源：** spec 2026-08-12-portability-reuse-design.md §5
- **执行者/分支：** （领取时填）

## 背景

平台两对等逻辑中，逻辑二「AI 生成 CAD」的 skill 域（aidxfv v1/v2 + aiblueprint-mcp）已交付，但业务逻辑核心 `services/cad` 待建。本轮仅锁定方向、立项占位，不动代码；下迭代作为入口实施。

## 涉及位置

- `services/cad/`（下迭代新建，本轮不碰）
- 下迭代先补独立 spec

## 方案

方向：与 `services/ifc` **完全同构**——
- DXF 生成脚本为唯一事实源（script-as-source）；
- 版本快照；
- 实体级语义 diff；
- REST 编辑 API 同形（PUT /script → run → save → locate）。

下一迭代先补独立 spec，再按 spec 实施。

## 验收标准

- 本 item 存在且方向写清（本轮验收仅此；实施验收由下迭代 spec 定）。

## 测试要求

- 本轮仅立项，无测试；实施时按下迭代 spec 的测试要求执行（预期与 services/ifc 同级：契约/沙箱/diff 全配测试）。
