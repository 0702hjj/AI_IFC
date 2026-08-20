# dispatch.md —— 线性逐 zone 执行与中断恢复

> 分工：**主 agent 亲自线性执行**——S2/S3 逐 zone 串行推进，不派发二级子代理；
> `aidxfv3 state` 负责状态记录。状态词表定义在 `state.json#state_machine`
> （mission 九态 / skeleton 四态）。

## 线性逐 zone（不并行）

异楼层 zone（裙房 / 塔楼）各自独立代表层、独立 mission，**顺序**推进——
`derived/floors.json#dag.edges` 恒空（position.on / vertical_relations 是几何/结构约束，
由 normalize 落位 + check_alignment_zones / check_core_alignment 校验）。

多 zone 起步：`aidxfv3 state sync --project <dir>` 补出全部 mission，再按 zones 顺序逐个处理：

```
对每个 mission（按 zones 顺序，前一个 done 才进下一个）：
  aidxfv3 pack --node <node> --project <dir>   # 渲染 mission（输入指针 + 知识注入）
  声明段：主 agent 读 missions/<node>/prompt.md + design/rooms.md → 写 rooms.json
          机器校验链（validate + normalize + check）→ 断点② 确认
  建造段：主 agent 读 design/details.md → 复制 skeleton.<floor>.dxf → 逐构件画 floor.dxf
  aidxfv3 state advance --project <dir> --node <node>   # 状态随产物推进
```

**每 zone 处理时按 include 声明加载参考提示**（design/rooms.md / design/details.md 头部的
`> include：...` 行）——rooms 的 include 链 = output_contract + work_area + draw_api +
draw_composition；details 的 include 链 = output_contract + work_area + draw_api。
主 agent 开工该 zone 时，把拼接后的全文读进上下文（draw 文档进上下文，画图调用面可见）。

## pack 知识注入（push 保底 + pull 精准）

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
**pull 精准**：主 agent 卡住时再 `gold query`（design/rooms.md 已教）。

## 完成即推进（主 agent 自校验，一行记录）

主 agent 完成一个 zone 后做状态记录与自查：

```
读 missions/<node>/ 的产物清单：
  rooms.json 在？floor.dxf 在？shot.svg 在？
  ├─ 声明段：跑 validate + normalize + check（声明合法性，唯一一次）
  │   通过 → status=presented 进断点②；error → 携报告修正声明
  ├─ 建造段：逐构件画完 floor.dxf → 集中跑 readback + reconcile
  │   （一次对账；检查在主 agent 侧执行）
  │   error → 携报告（带 bbox 诊断）修正建造（attempts+1）
  │   通过 → status=done
  └─ 缺产物 → 按中断恢复路由补（attempts+1）
attempts ≥3 → 升级：向用户说明现状，人工裁决该层去向
```

**上下文纪律**：每 zone 记录只留一行摘要 + 文件指针。细节留在文件里——
主线程装的是编排状态（小数据），线性推进不并行攒态。

## 升级与回滚

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。

- `geom_check_fail` → 携报告修正重做（attempts+1）；attempts≥3 → 主 agent 升级向用户裁决
- `skeleton_level_feedback` → skeleton 回 drafting，全部未 done mission 作废（唯一全局回滚）
- `reject_at_breakpoint` → 断点②拒绝 → 声明段回 `dispatched` 重做（携 feedback）
- `reconcile_fail` → 对账 error（画出来≠声明）→ 携报告修正建造；细节级（门窗/标注）走 details

## 中断恢复路由

`aidxfv3 state reconcile --project <dir>` 汇总全部 mission 真实状态（按产物推），按表恢复：

| 真实状态 | 恢复动作 |
|---|---|
| done | 已封存，跳过 |
| declared | 重跑 normalize/check 后重 present |
| presented | 断点确认后进建造 |
| built | 跑 readback + reconcile 后进 done |
| pending | 缺产物 → 从声明段重做 |
