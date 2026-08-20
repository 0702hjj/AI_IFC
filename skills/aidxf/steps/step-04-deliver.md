# step-04-deliver.md —— 交付 + 中断恢复

## 前置检查
- [ ] 全部 mission confirmed（S2/S3 完成）
- [ ] state.json 反映当前状态

## 信息源（本步需要的文件，够用即止）

- `references/machine_contract.md` —— deliver 命令契约（产物结构 + project 占位陷阱）
- `references/schemas/building.schema.json` —— building.json 契约
- `references/golden/` —— 已交付案例参照（deliver 产物形态）

## 动作

```bash
aidxfv3 deliver --project <dir>
```

## 产出
- `deliver/<floor>.dxf × N`（工程图纸）
- `deliver/<floor>.rooms.json × N`（封存声明）
- `deliver/building.json`（bim 接口：floors 映射 + checksums）

## 交付对象（外部接口）

| 交付物 | 消费方 | 说明 |
|---|---|---|
| `building.json` + 逐层 DXF + 封存 rooms | **下游 bim** | bim 接口文件 |
| `shot.svg` | **前端 viewer** | SVG 载体，`<img>`/inline 直渲 |
| plan.json | 上游 aiplan | 只读，全程不改 |

## 一致性自检
- [ ] building.json 过 references/schemas/building.schema.json
- [ ] 每层 DXF sha256 与 building.json checksums 对应
- [ ] 全部闸门（check/reconcile）最后一遍绿

> 中断恢复：`aidxfv3 state reconcile --project <dir>` 汇总真实状态，恢复路由见
> `references/orchestrator/dispatch.md`。

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **完成** → 交付摘要给用户（楼层数 + 面积 + 校验结论）
- **可选中：飞轮**（确认的好设计回流参考库）——走三闸门：
  1. **G1 源质量**：DXF 可 readback 解析（质量分 ≥ 阈值）
  2. **G2 replay 可重放**：`aidxfv3 gold replay --project <case_dir>` 过 normalize +
     reconcile（面积差 <5%），产 replay_check.json
  3. **G3 人工门**：template_worthy 人工判（值不值得教）
  三闸门过 → `gold ingest` + `gold reindex` → golden/ + golden.db（飞轮）
  任一 FAIL → 按闸门分流（G1 淘汰 / G2 进 _quarantine/）
