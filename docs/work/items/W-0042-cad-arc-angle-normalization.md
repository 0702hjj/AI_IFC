# W-0042: services/cad ARC 角度归一化——bulge 段 end 越界编码 + 跨零 ARC bounds 采样修复

- **状态：** open
- **优先级：** P2
- **Milestone：** v0.6（services/cad script-as-source）
- **来源：** chunk D Task 2 评审 2026-08-13（web dxfviewer 纯函数层 ARC sweep 裁决）
- **执行者/分支：** （领取时填）

## 背景

render payload v2 的 ARC 角度契约（`services/cad/app/render.py`）：原生 ARC 恒 CCW、`end < start` 表跨 0°；bulge 展开段 `end = start + 有向 sweep`（未归一化，`end ∉ [0,360)` 是有向 bulge 的判据）。存在两个服务端固有缺陷：

1. **bulge CW 段角度歧义**：bulge CW 段（sweep<0）若 `end = start + sweep` 恰好落回 `[0, start)`，则与原生跨零 ARC 在 payload 上不可区分（如 `start=100, sweep=−60 → end=40` vs 原生 `{start:100, end:40}`）。前端只能按原生跨零（CCW）解读，bulge CW 真值被画反/画大。web 侧已在 `arcSweep` 注释登记该歧义，根治需在服务端保持「`end ∉ [0,360)` ⟺ 有向 bulge」为完备判据。
2. **跨零 ARC bounds 漏采样（存量发现）**：`_entry_points` 对原生跨零 ARC（如 start=270, end=45）计算 `sweep = end − start = −225`（负数），`_angle_in_sweep` 按 CW 解读，0°/90°/180°/270° 极值点采样错误，bounds 可能漏掉极值（前端 fit 视图随之偏）。

## 涉及位置

- `services/cad/app/render.py`：`_arc_from_bulge`（end 编码）、`_transform`（INSERT 旋转后角度未归一）、`_entry_points` / `_angle_in_sweep`（跨零采样）
- 前端参照实现：`web/src/dxfviewer/geometry.ts` 的 `arcSweep`（平移归一 + 分支裁决，2026-08-13 fix）

## 方案

1. **bulge 段 end 越界编码**：`_arc_from_bulge` 中若 `end = start + sweep` 落回 `[0,360)` 且 sweep ≠ 0，将 end 减 360（sweep<0）或加 360（sweep>0），保持 `end ∉ [0,360)` ⟺ 有向 bulge 的完备判据。
2. **`_transform` 角度归一**：INSERT 旋转加完 rotation 后，start/end 同步平移回 `start ∈ [0,360)`（`k = floor(start/360)*360`，两端同减 k），与 web 侧 `arcSweep` 裁决对齐。
3. **`_entry_points` 跨零修复**：原生 ARC 的 sweep 计算改为 `sweep = (end − start) % 360`（恒 CCW）；bulge 段保持有向 sweep。`_angle_in_sweep` 配套复核。
4. 改动后跑 `cd services/cad && uv run --group dev pytest` 全绿，并 `services/ifc/scripts/export_openapi.py` 无需动（render.json 非 envelope 端点，schema 不变——仅角度值域语义收紧）。

## 验收标准

- bulge CW 段任意 start/sweep 组合下，payload 的 `end ∉ [0,360)` 判据完备（无落回歧义）。
- INSERT 旋转后的 ARC/bulge 子实体角度满足 `start ∈ [0,360)` 且 `end − start` 等于真值有向 sweep。
- 跨零原生 ARC（如 270→45）bounds 包含 0° 极值点；既有 209 测试不回归。
- web 侧 `arcSweep` 的歧义注释可更新为「服务端 W-0042 后判据完备」。

## 测试要求

- bulge CW 落回用例（start=100, sweep=−60 → end 编码为 −320，非 40）。
- INSERT 旋转归一用例（原生 ARC {10,50} + rotation −60 → {310,350}；bulge CW {300,−120 sweep} + rotation +90 → {30,−90}）。
- 跨零 ARC bounds 极值采样用例（270→45 含 0° 点 (cx+r, cy)）。
- 新增测试量 ≥ 新增实现量；`services/cad` 既有测试全绿。
