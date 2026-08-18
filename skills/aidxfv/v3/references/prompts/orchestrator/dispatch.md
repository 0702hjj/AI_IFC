# dispatch.md —— mission 派发与回收

> 分工：subagent 派发/回收由主 agent 用原生 agent 协议（task 派发，subagent 完成回来汇报）；
> `aidxfv3 state` 负责状态记录。状态词表定义在 `state.json#state_machine`（mission 九态 / skeleton 四态）。

## 就绪即派

异楼层 zone（裙房 / 塔楼）各自独立代表层、独立 mission，天然并行——
`derived/floors.json#dag.edges` 恒空（position.on / vertical_relations 是几何/结构约束，
由 normalize 落位 + check_alignment_zones / check_core_alignment 校验）。

多 zone 起步：`aidxfv3 state sync --project <dir>` 补出全部 mission，再逐个派发：

```
对每个 pending 的 mission：
  aidxfv3 pack --node <node> --project <dir>   # 渲染 mission（输入指针 + 知识注入）
  task 派 subagent（worker 类型 + 拼接模板）    # 原生 agent 协议——派发即放手，subagent 完成回来
  aidxfv3 state advance --project <dir> --node <node>   # 状态随产物推进
```

**派发时按 include 声明拼接模板**（worker 模板头部的 `> include：...` 行）——
floor_rooms.md 的 include 链 = shared/output_contract + work_area + draw_api + draw_composition，
主 agent 派发前把拼接后的全文交给 task 工具（draw 文档进 worker 上下文，画图调用面可见）。

## 派发时知识注入（pack）

`aidxfv3 pack` 渲染 mission 时，除输入指针外注入本层设计知识（LLM 写 rooms 的依据）：

```
① 本层骨架段：skeleton.json#zones[<zone>]（只读约束——core/corridor/partitions）
② gold pattern 命中段：按本层 program 房间类型 + 痛点预筛
   aidxfv3 gold query --params '{"kind":"pattern","pain":"P2-x","type":"<function>"}'
   → 命中 pattern 的 DSL 片段注入 mission prompt（机器预筛）
③ 案例骨架封装（可选）：形态把握不准时
   aidxfv3 gold query --params '{"kind":"case","type":"<function>"}' → skeleton_dsl
```

**push 保底**：pack 时机器按类型 + 痛点选段注入（K1 最小注入纪律）；
**pull 精准**：worker 卡住时再 `gold query`（floor_rooms.md 已教）。

## 回收（一行摘要纪律）

subagent 按原生 agent 协议完成并汇报后，主 agent 做状态记录：

```
读 missions/<node>/ 的产物清单：
  rooms.json 在？floor.dxf 在？shot.svg 在？
  ├─ 声明段：主 agent 跑 validate + normalize + check（声明合法性，唯一一次）
  │   通过 → status=presented 进断点②；error → 携报告重派声明
  ├─ 建造段：worker 画完 floor.dxf 返回 → 主 agent 集中跑 readback + reconcile
  │   （一次对账；检查在主 agent 侧执行）
  │   error → 携报告（带 bbox 诊断）重派建造（attempts+1）
  │   通过 → status=done
  └─ 缺产物/未返回 → 判死重派（attempts+1）
attempts ≥3 → 升级：主 agent 亲自带全部历史处理该层，断点内向用户说明
```

**上下文纪律**：worker 返回只收一行摘要 + 文件指针。细节留在文件里——
并行 N 个 worker 时主线程装的是编排状态（小数据）。

## 升级与回滚

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。

- `geom_check_fail` → 携报告自动重派（attempts+1）；attempts≥3 → 主 agent 接管
- `skeleton_level_feedback` → skeleton 回 drafting，全部未 done mission 作废（唯一全局回滚）
- `reject_at_breakpoint` → 断点②拒绝 → 声明段回 `dispatched` 重派（携 feedback）
- `reconcile_fail` → 对账 error（画出来≠声明）→ 携报告重派建造；细节级（门窗/标注）走 details

## 中断恢复路由

`aidxfv3 state reconcile --project <dir>` 汇总全部 mission 真实状态（按产物推），按表恢复：

| 真实状态 | 恢复动作 |
|---|---|
| done | 已封存，跳过 |
| declared | 重跑 normalize/check 后重 present |
| presented | 断点确认后进建造 |
| built | 跑 readback + reconcile 后进 done |
| pending | 缺产物 → 重派 |

