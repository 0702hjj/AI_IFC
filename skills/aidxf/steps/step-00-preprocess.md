# step-00-preprocess.md —— S0 预处理（断点⓪ 确认后进 S1）

## 前置检查
- [ ] `plan.json` 存在（aiplan 产物，只读输入）
- [ ] `aidxfv3` CLI 可用

## 信息源（本步需要的文件，够用即止）

- `references/machine_contract.md` —— preprocess 命令契约（输入输出 schema / 退出码）

## 动作

```bash
aidxfv3 preprocess --plan <plan.json> --out derived/
```

## 产出
- `derived/floors.json`（代表层归并 + DAG + 校验参数）
- `derived/<zone>.json × M`（zone 包：geom 派生 + 代表层切片 + vocab + 金例卡片）
- `derived/skeleton_base.json`（底座：outline/core anchor 从 plan 机械注入，S1 主 agent 在其上全权填充）

## 断点⓪（S0 确认——ask_user 弹框）

S0 退出码 0 后，回显 S0 摘要（zone 数 + 总面积 + 每 zone 形态要点）→ `ask_user` 弹框确认：

```
question({
  question: "S0 预处理完成：{N} 个 zone，总面积 {X}㎡，轮廓已注入底座。
    （简述各 zone 形态：塔楼/板式/裙房…）——进 S1 骨架设计，对吗？",
  header: "S0 确认（断点⓪）",
  options: [
    {label: "对，进 S1", description: "S0 产物确认，开始骨架设计"},
    {label: "改 plan / 重跑", description: "plan 或预处理有问题，告诉我改哪里"}
  ],
  custom: true
})
```

> S0 是纯机器步骤但设确认点：S0 完弹 question，用户确认后进 S1。S1→断点①、S2→断点② 同理，
> 每个阶段边界都有 question。

## 停步/路由
- **FAIL**（退出码 1/2）→ 停步，向用户报 plan schema / 轮廓级摄取错误，进入断点⓪ 前修正
- **断点⓪ 确认** → 路由到 `step-01-skeleton.md`
