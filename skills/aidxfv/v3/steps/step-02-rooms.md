# step-02-rooms.md —— S2 房间设计 + 断点②

## 前置检查
- [ ] skeleton.json 已冻结（断点① 确认）
- [ ] state.json 的 DAG 就绪

## 信息源（本步需要的文件，够用即止）

- `references/machine_contract.md` —— rooms normalize/check/readback/reconcile 契约 + 坐标归一化陷阱
- `references/schemas/rooms.schema.json` —— rooms DSL 契约
- `references/prompts/worker/floor_rooms.md` —— 房间分墙规范（承接分区/墙声明/标签）
- `references/draw_api.md` —— 画墙调用面（wall_run/door/window/room_label 签名）
- `references/prompts/worker/floor_details.md` —— 门窗统一规律
- 房间写法库（`references/room_patterns/`）+ 金例按需取用

## 动作（主 agent 调度，rooms-worker 执行）

1. **就绪即派**（orchestrator/dispatch.md）：
   ```bash
   aidxfv3 pack --node <zone>.<stage> --project <dir>   # 渲染 mission
   ```
   → task 派 rooms-worker（worker/floor_rooms.md）
2. **回收**（一行摘要纪律）：
   - 声明段产物齐（rooms.json）→ 机器校验链（**声明合法性，唯一一次**）：
     ```bash
     aidxfv3 validate --dsl missions/<node>/rooms.json
     aidxfv3 normalize --dsl <rooms> --params <skeleton.json>   # DSL 自动过 normalize_skeleton
     aidxfv3 check --plan <plan.json>                             # 轮廓级摄取
     aidxfv3 check --dsl <rooms> --geom <skeleton.json>         # 房间级 R-01~R-09
     ```
   - 通过 → 进 presented 队列（画完后 check 声明侧，声明未变即成立）
3. 【断点② 用户逐层确认】（单断点纪律，其余排队）——用 `question` 工具弹框
   （方式见 `references/prompts/orchestrator/breakpoint.md`）：
   对话回显该层房间方案 → `question` 弹"对吗？对，继续 / 改房间 / 骨架问题"（custom:true）
   ——改同板块→再问同板块（修改协议）
4. 确认后 worker 进建造段：复制 skeleton.<floor>.dxf → 逐构件画 floor.dxf
   → 落盘 → 返回一行摘要（检查在主 agent 侧执行）
5. 回收后主 agent 集中执行：**readback + reconcile**（一次对账）
   ├─ error → 携报告（带 bbox 诊断）重派建造（attempts+1）
   └─ 通过 → 进 done

## 产出
- `missions/<node>/`（mission.json + rooms.json + floor.dxf + shot.svg + geom_check.json）

## 停步/路由

> 回退规则单处定义：`state.json#state_machine.rollback_rules`。
- **geom_check FAIL** → 携报告自动重派（attempts+1）
- **断点② 局部修改** → feedback.md + 重派该 mission
- **断点② 骨架级意见** → 回 step-01（唯一全局回滚）
- **attempts ≥3** → 主 agent 亲自接管该层
- **会话中断** → `aidxfv3 state reconcile --project <dir>` 汇总真实状态后按
  `references/prompts/orchestrator/dispatch.md` 恢复
- 全部 done → 路由到 `step-03-details.md`
