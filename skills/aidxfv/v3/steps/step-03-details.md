# step-03-details.md —— S3 最后一步：门窗统一规律 + 柱网 + 标注

## 前置检查
- [ ] 该层 rooms confirmed（断点② 通过）
- [ ] floor.dxf 建造完成

## 信息源（本步需要的文件，够用即止）

- `references/draw_api.md` —— door/window/draw_column/draw_dim_chain 签名
- `references/draw_composition.md` —— 整层组装序（底座→墙→门窗→柱→标注→封存）
- `references/prompts/worker/floor_details.md` —— 门窗统一规律 / 柱网 / 标注
- `references/machine_contract.md` —— readback/reconcile 单向防多语义 + 坐标平移

## 动作（主 agent 调度，details-worker 执行）

1. 派 details-worker（worker/floor_details.md）：
   ```bash
   aidxfv3 pack --node <zone>.details --project <dir>
   ```
2. 回收：门窗（统一规律批量生成，见 floor_details.md）/ 柱网/标注 → 落盘 → 主 agent 跑 readback + reconcile
3. 房间划分保持原样（reconcile 兜底）

## 完成后闸门（details 必过）

```
aidxfv3 svg --dxf floor.dxf --out shot.svg     # 视觉自检
aidxfv3 check --plan <plan.json>                  # 机检
aidxfv3 readback --dxf floor.dxf                # 回读
aidxfv3 reconcile --decl rooms.json --graph <回读图>   # 对账（划分变更兜底）
```

- **对账 FAIL**（房间划分被改/墙段缺失）→ 携报告重派（attempts+1），回 details-worker
- **attempts ≥3** → 主 agent 接管该层
- **shot.svg 可选呈现用户**（细节级异议 → feedback 重派建造，JSON 保持）

## 产出
- `missions/<node>/floor.dxf`（增量画细节）

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **FAIL** → 携报告重派（attempts+1）
- 全部 done → 路由到 `step-04-deliver.md`
