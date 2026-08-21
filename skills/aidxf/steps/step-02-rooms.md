# step-02-rooms.md —— S2 房间设计 + 断点②（线性逐 zone）

## 前置检查
- [ ] skeleton.json 已冻结（断点① 确认）
- [ ] state.json 的 DAG 就绪

## 信息源（本步需要的文件，够用即止）

- `references/machine_contract.md` —— rooms normalize/check/readback/reconcile 契约 + 坐标归一化陷阱
- `references/schemas/rooms.schema.json` —— rooms DSL 契约
- `references/design/rooms.md` —— 房间分墙规范（承接分区/墙声明/标签，含 include 链）
- `references/draw_api.md` —— 画墙调用面（wall_run/door/window/room_label 签名）
- `references/design/details.md` —— 门窗统一规律（建造段）
- 房间写法库（`references/room_patterns/`）+ 金例按需取用

## 动作（主 agent 亲自，线性逐 zone，按 orchestrator/dispatch.md）

对每个 zone mission（按 zones 顺序，前一个 done 才进下一个）：

1. **渲染 mission + 加载参考提示**（prompt 参考加载逻辑与逐 zone 任务包一致）：
   ```bash
   aidxfv3 pack --node <zone>.rooms --project <dir>   # 渲染 mission（输入指针 + 知识注入）
   ```
   → 主 agent 读 `missions/<zone>.rooms/prompt.md` + `design/rooms.md`
   （按 include 声明拼入 output_contract + work_area + draw_api + draw_composition）
   → 在该 zone 承接分区内写 `rooms.json`（声明段）
2. **机器校验链**（声明合法性，唯一一次）：
   ```bash
   aidxfv3 validate --dsl missions/<node>/rooms.json
   aidxfv3 normalize --dsl <rooms> --params <skeleton.json>   # DSL 自动过 normalize_skeleton
   aidxfv3 check --plan <plan.json>                             # 轮廓级摄取
   aidxfv3 check --dsl <rooms> --geom <skeleton.json>         # 房间级 R-01~R-09
   ```
   - 通过 → 进 presented 队列；error → 携报告修正声明（attempts+1）
3. 【断点② 用户确认该 zone】（单断点纪律，其余 zone 排队）——用 `ask_user` 工具弹框
   （方式见 `references/orchestrator/breakpoint.md`）：
   对话回显该 zone 房间方案 → `question` 弹"对吗？对，继续 / 改房间 / 骨架问题"（custom:true）
   ——改同板块→再问同板块（修改协议）
4. 确认后进入该 zone 建造段：复制 `skeleton.<floor>.dxf` → 逐构件画 `floor.dxf`
   （draw_api 画法调用面）→ 落盘
5. **readback + reconcile**（一次对账，主 agent 集中执行）
   ├─ error → 携报告（带 bbox 诊断）修正建造（attempts+1）
   └─ 通过 → `aidxfv3 state advance --project <dir> --node <zone>.rooms` → done → 下一个 zone

## 产出
- `missions/<zone>.rooms/` × 全部 zone（mission.json + rooms.json + floor.dxf + shot.svg + geom_check.json）

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **geom_check FAIL** → 携报告修正重做（attempts+1）
- **断点② 局部修改** → feedback.md + 该 mission 修正重做
- **断点② 骨架级意见** → 回 step-01（唯一全局回滚）
- **attempts ≥3** → 主 agent 升级向用户说明、人工裁决
- **会话中断** → `aidxfv3 state reconcile --project <dir>` 汇总真实状态后按
  `references/orchestrator/dispatch.md` 恢复
- 全部 done → 路由到 `step-03-details.md`
