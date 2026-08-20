# step-03-details.md —— S3 最后一步：门窗统一规律 + 柱网 + 标注（线性逐 zone）

## 前置检查
- [ ] 该层 rooms confirmed（断点② 通过）
- [ ] floor.dxf 建造完成

## 信息源（本步需要的文件，够用即止）

- `references/draw_api.md` —— door/window/draw_column/draw_dim_chain 签名
- `references/draw_composition.md` —— 整层组装序（底座→墙→门窗→柱→标注→封存）
- `references/design/details.md` —— 门窗统一规律 / 柱网 / 标注（含 include 链）
- `references/machine_contract.md` —— readback/reconcile 单向防多语义 + 坐标平移

## 动作（主 agent 亲自，线性逐 zone）

对每个 zone mission（按 zones 顺序推进）：

1. **加载参考提示**：主 agent 读 `design/details.md`
   （按 include 声明拼入 output_contract + work_area + draw_api）
2. **增量画细节**：门窗（统一规律批量生成，见 details.md）/ 柱网/标注
   → 在 `floor.dxf` 上逐构件画 → 落盘
3. **readback + reconcile**（主 agent 集中执行）：房间划分保持原样（reconcile 兜底）

## 完成后闸门（details 必过）

```
aidxfv3 svg --dxf floor.dxf --out shot.svg     # 视觉自检
aidxfv3 check --plan <plan.json>                  # 机检
aidxfv3 readback --dxf floor.dxf                # 回读
aidxfv3 reconcile --decl rooms.json --graph <回读图>   # 对账（划分变更兜底）
```

- **对账 FAIL**（房间划分被改/墙段缺失）→ 携报告修正（attempts+1），回本 zone 细节重做
- **attempts ≥3** → 主 agent 升级向用户说明、人工裁决
- **shot.svg 可选呈现用户**（细节级异议 → feedback 修正建造，JSON 保持）

## 产出
- `missions/<node>/floor.dxf`（增量画细节）——全部 zone 完成后进 S4

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **FAIL** → 携报告修正（attempts+1）
- 全部 done → 路由到 `step-04-deliver.md`
