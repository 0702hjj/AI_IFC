# step-04-deliver.md —— S4 交付改造（固化 → 注册平台模型 → building.json）+ 中断恢复

> S4 交付改造（2026-08-21 起）：**不再「复制 DXF 到 deliver/」**——deliver 的 DXF 交付被
> script 工具链替代（init_model + stage/run/save 注册平台模型），building.json 保留（zones 记
> modelId），deliver 后清理中间产物（再次修改走平台模型 script-as-source）。

## 前置检查
- [ ] 全部 mission confirmed（S2/S3 完成）
- [ ] state.json 反映当前状态
- [ ] S2/S3 画图时已开 record 记录（`record.start()` + `record.wrap_draw_module(draw)`）

## 信息源（本步需要的文件，够用即止）

- `references/machine_contract.md` —— S4 交付改造契约（record 固化 + script 工具链 + 工作区 + 清理）
- `references/schemas/building.schema.json` —— building.json 契约（zones 记 modelId）
- `references/draw_composition.md` —— record 记录 + build() 脚本固化（出口）

## 动作（三子步）

### S4-a 固化每 zone build() 脚本

每 zone 画图（S2/S3）时已记录 draw 调用序列，本步固化为构建脚本：
```python
from dxfkit import record
script = record.to_build_script(record.calls(),
                                params={...})  # skeleton/rooms/details DSL
# → archdxf 可运行的 build() 脚本（PARAMS + build(params,out_path) + __main__，
#   对齐 services/cad script-as-source 契约）——该 zone 的构建脚本事实源
```

### S4-b 注册平台模型（每 zone，init_model 前置）

对每 zone 经 script 工具链注册为平台模型（**替代旧 deliver 的复制 DXF**）：
```
init_model(dxf, title=zone名)        ← 分配 modelId + 建骨架（前置）
stage_script(build() 脚本)            ← 暂存该 zone 构建脚本
run_script()                          ← 沙箱跑 build 产 DXF（共享画法层 archdxf/dxfkit）
save_script()                         ← 落 v1 版本（scripts/v1.py + DXF 快照）
```
→ 每 zone DXF 成为**平台模型**（modelId + script-as-source 版本化 + viewer render.json 可看）。

### S4-c building.json 组装（agent 侧，非 CLI deliver）

> `aidxfv3 deliver` 命令已退役（2026-08-21）——它的两个职责（复制 DXF + 汇总 building.json）
> 都被 agent 工具链替代：复制 DXF → S4-b script 工具链；building.json → 本步 agent 组装
> （deliver.py 不知道 agent init_model 的 modelId，产不了 zones 的 modelId 指针）。

agent（你）组装 building.json 并交付：
```
# 1. 组装 building.json 内容：
#    读 plan.json（get_project_plans）+ 各 zone modelId（S4-b init_model 返回）
#    → plan 形态整栋楼（site/standards/vertical_relations/design_rationale/requirements
#      原样来自 plan）+ zones[]（每 zone：floors_from/to + modelId + 非几何属性 typology/note/area）
# 2. deliver_building 工具交付：
deliver_building(building=<组装内容>)
#    → PlanStore 版本化 plans/{projectID}/building.json（+ plan_history/v{n} 归档）
```
→ building.json 落方案库（plans/{projectID}/），zones 记 **modelId**——ifc 经 get_project_plans
（扩展读 building.json）拿 zones→modelId 映射，再 get_project_models/get_script 拿各 zone DXF
平台模型。

## 产出
- **每 zone 平台模型**（modelId + build() 脚本 + DXF，script-as-source 版本化）——S4-b
- `deliver/building.json`（bim 接口：plan 形态整栋楼 + zones 记 modelId）——S4-c

## 交付对象（外部接口）

| 交付物 | 消费方 | 说明 |
|---|---|---|
| `building.json`（记 modelId）+ 各 zone 平台模型 | **下游 bim** | bim 接口文件 + 平台模型（经 modelId 拿 DXF） |
| `shot.svg` | **前端 viewer** | SVG 载体，`<img>`/inline 直渲 |
| plan.json | 上游 aiplan | 只读，全程不改 |

## deliver 后清理中间产物

S4 完成后**清空工作区过程产物**（missions/derived/floor.dxf 过程态）：
- 事实源已转移到平台模型 build() 脚本（models/{modelId}/scripts/）——再次修改走平台模型
  script-as-source（改 build 脚本 → 沙箱跑 → 新版本），**不依赖中间产物**。
- 残留的过程文件（missions/prompt/floor.dxf 过程态）只会在再次修改时误导（以为要按
  missions/derived 继续，其实该改平台模型脚本）——故清理。
- 保留：平台模型的 build() 脚本 + DXF（models/{modelId}/）+ building.json（方案/项目级）。

## 一致性自检
- [ ] 每 zone 已注册平台模型（get_project_models 可见 modelId + ready）
- [ ] building.json 过 references/schemas/building.schema.json（zones 记 modelId）
- [ ] 全部闸门（check/reconcile）最后一遍绿
- [ ] 中间产物已清理（再次修改走平台模型 script-as-source）

> 中断恢复：`aidxfv3 state reconcile --project <dir>` 汇总真实状态，恢复路由见
> `references/orchestrator/dispatch.md`。

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **完成** → 交付摘要给用户（楼层数 + 各 zone modelId + 面积 + 校验结论）
- **可选中：飞轮**（确认的好设计回流参考库）——走三闸门：
  1. **G1 源质量**：DXF 可 readback 解析（质量分 ≥ 阈值）
  2. **G2 replay 可重放**：`aidxfv3 gold replay --project <case_dir>` 过 normalize +
     reconcile（面积差 <5%），产 replay_check.json
  3. **G3 人工门**：template_worthy 人工判（值不值得教）
  三闸门过 → `gold ingest` + `gold reindex` → golden/ + golden.db（飞轮）
  任一 FAIL → 按闸门分流（G1 淘汰 / G2 进 _quarantine/）
