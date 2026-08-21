# W-0052: cad→ifc 消化管线重点完善 + 系统化实验

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.13（见 PLAN-v0.1.0.md）
- **来源：** 2026-08-21 用户裁决：「最后还需要重点完善的是 cad->ifc 的这个消化管线，还需要多做实验」
- **执行者/分支：** （领取时填）
- **GitHub Issue：** #69（https://github.com/0702hjj/AI_IFC/issues/69）

## 背景

cad→ifc 消化管线（aiifc skill `consume_upstream` → `design-build` → `build-script`）已实现并通过基础端到端（building.json + 各 zone DXF → design.json → features.json → 演示 IFC，2026-08-21 全链实测通过）。但这是**初始消化版本**——真实 cad 产物的形态远比测试样例复杂，需要：

1. **多做实验**：用不同建筑形态的 cad 产物（多 zone、多楼层、曲线墙、门窗定位、楼梯、斜屋顶、特殊结构）系统跑 consume_upstream → design-build → build-script，收集消化质量数据。
2. **重点完善**：根据实验结果补齐消化管线缺口——DXF 解析鲁棒性、design.json 语义保真、跨 zone 一致性、IFC 产出规范。
3. **深水区已知待查**：
   - 多 zone 的 `floors_from/floors_to` 在 consume_upstream 里的楼层映射是否保真。
   - 曲线（arc）在 consume_upstream 读 DXF 后进 design.json 的几何表达是否可用（arc→ifc 的 IfcPolyline 分段？还是 IfcTrimmedCurve？）。
   - 门窗定位（door/window anchors）从 DXF 层名 → design 开口 → build 脚本的 IFC 构件全链是否一致。
   - `dxfkit.readback`（editable 装进 skills/.venv）在真实 execute 路径的稳定性（已实测单次 OK，需多形态验证）。

## 涉及位置

- `skills/aiifc/scripts/aiifc_cli/aiifc/`（cli.py：consume-upstream / design-build / build-script / --project-id）
- `skills/dist/aiifc/references/consume_upstream/`（管线说明）
- `skills/aiifc/references/docs/flows/`（design_builder / build_script_template / consume_upstream）
- `skills/aiifc/tests/`（test_consume_upstream / test_cli_project_id）

## 方案

1. **实验矩阵**：建一套 cad 产物 fixture 库（至少 6 种形态：单 zone 标准层 / 多 zone / 多楼层 / 曲线墙 / 门窗定位 / 楼梯+斜屋顶），每种跑「consume-upstream → design-build → build-script」全链，记录设计保真度。
2. **消化管线补齐**：按实验结果修 consume_upstream 的解析缺口（曲线、门窗、楼层映射、多 zone 合并）+ design_builder 的语义保真 + build_script_template 的 IFC 规范产出。
3. **回归**：现有 15 个 aiifc 测试保持绿，新增实验形态的消化契约测试。

## 验收标准

- 实验矩阵全跑通：至少 6 种 cad 形态的 consume-upstream → design-build → build-script 全链成功（产物规范落 skill-work/{projectID}/）。
- 消化质量有数据：每种形态记录 design.json/features.json/IFC 的保真度结论（哪些保真、哪些丢、哪些需人工补）。
- 管线缺口按实验结论修复，新增契约测试覆盖新形态。
- 中间产物落盘纪律保持：--project-id → skill-work/{projectID}/；build 脚本+IFC 版本化走 models/{modelId}/。

## 测试要求

- 新增消化管线测试：实验 fixture 每种形态至少 1 个契约测试（consume-upstream → design-build → build-script 断言产物规范）。
- 测试量 ≥ 实现量。
