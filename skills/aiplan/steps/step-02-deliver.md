# step-02 生成落盘（P2 交付）

> 把 step-01 全锁定的设计草案 → 待落盘的 plan.json + bim_supplement.json → 成对落盘 + 双下游告知。
> **无权改意图，只有生成权**（step-01 锁定后意图不可变）。

## 输入

- step-01 渐进设计对话全锁定的草案（4 轮：骨架/几何/功能/结构空间）
- 或：中断恢复——plan/ 下已有完整 run 目录（直接校验该 run，见路由）

## 机器动作（确定性）

1. **按已锁定轮次组装**：只组装 4 轮全锁定的字段——未锁定轮不得落盘
   （防御：确认不完整时拒绝生成）
2. 组装为 plan.json（严格按 `references/schemas/plan.schema.json` 契约）：
   - 各 zone 的 `outline_mm` / `core` polygon / `core_anchor_mm`（第 2 轮几何产物）
   - `program` / `area_allocation`（第 3 轮功能产物，含 core/service_core 拆分）
   - `requirements` / `standards`（第 3 轮规范产物）
   - **zone_split**：分裂 zone（S1-S3）→ 组入 zones[] + vertical_relations 链式 zone_split 记录
3. `aiplan validate plan` schema 门禁（自持 `references/schemas/plan.schema.json`）
4. **设计质量门禁**（`aiplan gate <plan.json>`，2026-08-11——把"可选流程"升级为强制门禁）：
   - `design_rationale` **必填**（设计推理显式化）
   - 必须引用 ≥1 个 derive 事实字段（aspect_ratio/exposure_m/deep_zone_ratio/dominant_axes/concave_corners/buildable_*）
   - 落盘前用 lot+setbacks 实跑 `derive` 机检引用字段真实存在
   - **形态真实性检查（强制）**：长板地块但 outline 各边仅 2 点、无任何凹凸/切角/弧表达 → **FAIL 拒绝落盘**，回 step-01 第 2 轮补形态
    - **FAIL → 拒绝落盘，回 step-01 第 2 轮**（derive → index 命中 pattern → 读 1 个 golden → 写 rings intent）
5. **对齐校验（S3）**：`aiplan geom align --zones '<zones JSON>'`——核心筒 shape 跨层一致
   （(area,w,h) 相同）+ core ⊆ outline；FAIL → 回 step-01 修对齐
6. `aiplan canon` canon 序列化 + sha256
7. bim_supplement 同理：`aiplan validate bim` 双门禁（schema + 语义，语义校验含
   bim_supplement_lint 的 type-字段配对/常识下限/去重）；`source_plan_sha256` = plan.json canon sha

## 模型动作

- 只在用户未指定维度做**受限创新**（候选集内选优 / 区间内取值 / prefer 项排序）
- **不突破**任何用户意图与硬约束

## 落盘（run 目录唯一性，零覆盖）

```
.venv/bin/aiplan land <plan.json> <bim_supplement.json> --outdir plan/
# 落盘到 {workspace}/plan/<时间戳>_<项目>/
#   ├─ plan.json            ★任务书事实源★（canon 后冻结）
#   └─ bim_supplement.json  ★BIM 补充事实源★（成对，sha256 互指）
```
**唯一性**：每次 `aiplan land` **单开 run 目录**——不覆盖任何历史，每次设计是一个独立 run，
全程可追溯。同秒同名自动加 `_2` 序号防碰撞。下游读取 = 指定 run 目录。

## 路由（中断恢复，D-4——判定规则见 step-00，此处只收尾）

```
plan/ 下有完整 run（已冻结）→ 跳过 step-01，本步直接校验该 run 内文件
                        （重读 + 双门禁 + 互指校验，通过即完成）
plan/ 下无完整 run → 必须从 step-00 走完整 P0→P2
```

## 校验（完成标志）

- `land_pair.py` 退出码 0 + 两文件存在 + 互指校验通过 → P2 完成
- plan.json 过自持 schema 门禁 + canon + sha256
- bim_supplement 过自持 schema + 参数取自持 `references/bim_param_defaults.md`
- 落盘后重读校验 source_plan_sha256 一致（防御性 assert）

## 交付告知（双下游）

- **cad 段**：读取本次 run 目录内 `plan.json` 摄取（schema 见本 skill 自持副本）
- **bim 段**：读取本次 run 目录内 `bim_supplement.json`，按
  `references/schemas/bim_supplement.schema.json` 映射写回 IFC 属性
