# step-01-skeleton.md —— S1 骨架设计 + 断点①

## 前置检查
- [ ] `derived/` 齐（断点⓪ 已确认通过）
- [ ] 读全部 zone 包 geom 段（设计素材来自 derived/）
- [ ] 读 `derived/skeleton_base.json`（底座：outline/core anchor 已从 plan 机械注入）

## 信息源（本步需要的文件，够用即止）

- `derived/` —— 设计素材（zone 包 geom 派生事实 + skeleton_base 底座）
- `references/machine_contract.md` —— validate/normalize/check 命令契约 + 锚点 `at` 精度陷阱
- `references/orchestrator/skeleton.md` —— 骨架设计规范（分层外推/切割线/blocks 写法）
- `references/schemas/skeleton.schema.json` —— 骨架 DSL 契约
- 类型包（`references/building_types/residence/`）+ 金例（`aidxfv3 gold query`）按需取用

## 动作（主 agent 亲自，按 orchestrator/skeleton.md）

1. **在底座上填充** `skeleton.json`（从 `skeleton_base.json` 出发，全权修改；
   补 typology/形态族/core vertices（或 path 分段）/corridor/main_partitions 切割线/blocks 等，每 zone ≤5 决策，
   typology_reason 引用 geom 事实；轴网由机器派生）
2. 机器校验链：
   ```bash
   aidxfv3 validate --dsl skeleton.json          # schema（exit 2 → 回改）
   aidxfv3 normalize --dsl skeleton.json          # 几何坐标（唯一坐标计算点）
   aidxfv3 check --plan <plan.json>                 # 轮廓级摄取（exit 1 → 回改）
   aidxfv3 check --dsl skeleton.json --plan <plan.json>  # 骨架级：分区越轮廓 + blocks 语义 + holes 对齐
   ```
3. 【断点① 用户确认】——用 `question` 工具弹框（方式见 `references/orchestrator/breakpoint.md`）：
   对话回显骨架方案（建筑师语言）→ `question` 弹"对吗？对，继续 / 要改骨架"（custom:true）
4. 确认后：按代表层出 `skeleton.<floor>.dxf`（分区轮廓底座 = dxfkit 按 normalize 分区几何画；
   LLM 在底座上逐构件画画法细节，`aidxfv3 draw`）→ 骨架冻结

## 产出
- `skeleton.json`（**项目根**，冻结后只读——全局一份，含全部 zone）
- `preview.skeleton.svg`（断点呈现物，用后即弃）
- `missions/<zone>.rooms/skeleton.<zone>.dxf × N`（**各代表层底图，放对应 zone 的 mission 目录**——
  S2 主 agent 从这里复制为 floor.dxf，一条 DXF 链）

## 停步/路由
- **用户骨架级意见** → 回本步改 skeleton.json（唯一全局回滚点）
- **断点①确认** → 路由到 `step-02-rooms.md`
- **FAIL**（schema/normalize/check）→ 回本步改声明，进入断点前修正
