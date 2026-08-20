# W-0049: 文件行数门控合规重构——白名单 19 项拆分收口

- **状态：** done（关闭于 PR #48~#52；白名单已收敛到 4 项，仅余 W-0048 范围）
- **优先级：** P2
- **Milestone：** v0.12（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-20 用户裁决：「看代码硬规则，本仓不符的需要重构」
- **执行者/分支：** kimi-code / 按组件分支序列（见下）

## 背景

AGENTS.md「代码门控」要求源码/文档 ≤500 行，存量超限登记在
`scripts/file_size_whitelist.txt`（只减不增）。登记时共 25 项，其中
`docs/superpowers/plans/` 下 6 份为**已执行完毕的历史 plan 归档**（最大 2611 行）
——拆分会破坏考古价值，2026-08-20 用户裁决改为 gate 豁免类别
（与 generated/golden/research 同级），白名单真实收窄到 19 项。

## 涉及位置（19 项，按组件分 PR）

- server：`internal/agent/tools_test.go`（709）、`internal/api/chat_tools_test.go`（567）
- web：`src/viewer/ChatSidebar.tsx`（524）、`src/viewer/ChatSidebar.test.tsx`（506）、`src/dxfviewer/DxfViewer.test.tsx`（606）
- skills/aiifc：`references/docs/flows/design_review.py`（1194）
- skills/aidxfv/v3：`dxfkit/readback.py`（1158）、`floorgeom/normalize.py`（665）、`floorgeom/derive.py`（513）、`tests/test_normalize.py`（551）、`tests/test_goldlib.py`（527）
- skills/aiplan：`aiplan_tools/normalize.py`（568）
- tests/skill：`test_skill_hooks.py`（591）
- docs：`scripts/go-openapi-schema.mjs`（974）、`site/reference/edit-api-reference.md`（920）
- **不在本项**：`services/{ifc,cad}/app/routes_scripts.py` 与 `tests/test_script_runner.py`（4 项）——W-0048 沙箱设计修正将合并双 runner 并重写这些文件，现在拆分是重复劳动，留给 W-0048 顺手收口

## 方案

1. gate 豁免历史 plan 归档 + 白名单删 6 项（本项首个 PR 已含）。
2. 按组件分 PR 拆分剩余 15 个文件：测试文件按领域拆成多个测试文件（pytest/go test/vitest 均支持同目录多文件发现）；源码按职责拆模块，公开入口保持不变（facade/re-export 或同包多文件）。
3. 每拆完一个文件即从白名单删除对应行；PR 合并前白名单只减不增。
4. 纯重构纪律：不改行为、不改测试断言语义；split 后对应组件测试套件必须全绿。

## 验收标准

- 白名单从 19 项收敛到 4 项（仅剩 W-0048 范围的 routes_scripts.py ×2 + test_script_runner.py ×2）。
- `bash scripts/check_file_size.sh` 绿；涉及组件的测试套件全绿（server/web/skill/aiplan/aidxfv/docs 各自现有命令）。
- 每个 PR 只含一个组件的拆分，无行为变化。

## 测试要求

- 纯重构不新增行为，不强制新增测试；但拆分测试文件时用例总数不得减少（拆分前后 `pytest --collect-only -q` / `go test -list` / vitest 用例数对比留证）。
