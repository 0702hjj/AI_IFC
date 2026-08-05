# P0-2: dxf_from_design 楼梯 shaft KeyError

- **状态：** open
- **优先级：** P0
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

design_builder 在 normalize 阶段已把楼梯的 shaft 展开为 `{x0,x1,y0,y1}` 坐标矩形；但 dxf_from_design 的楼梯分支仍按轴网索引 `s["x"][0]` 的旧格式读取，含 shaft 的楼梯必然抛 KeyError，导致此类 design JSON 无法出 DXF。CI 冒烟 fixture（tests/skill/fixtures/sample_design.json）不含楼梯，绕开了此路径，因此问题未被 CI 捕获。

## 涉及位置

- `skills/aiifc/references/docs/flows/design_builder.py:114-119` — shaft 展开为 `{x0,x1,y0,y1}` 坐标矩形
- `skills/aiifc/references/docs/flows/dxf_from_design.py:141-147` — 楼梯分支仍按轴网索引 `s["x"][0]` 读取
- `tests/skill/fixtures/sample_design.json` — CI 冒烟 fixture 不含楼梯

## 方案

把 dxf_from_design.py 的楼梯分支改为读取 `{x0,x1,y0,y1}` 坐标矩形，与 design_builder 的 normalize 输出对齐；为兼容 design JSON 原始输入（未经 normalize 的轴网索引格式），输入先经 `design_builder.normalize` 处理后再生成 DXF，保证两种输入路径都可用。

## 验收标准

含 shaft 楼梯的 design JSON 能成功生成 DXF，不抛 KeyError，且楼梯实体落在 STAIR 图层。

## 测试要求

1. 新增含 shaft 楼梯的 fixture，跑 dxf_from_design，断言输出图层含 STAIR 实体且不抛 KeyError。
2. CI skill-pack 的冒烟 fixture 同步加入楼梯，防止该路径再次绕过测试。
