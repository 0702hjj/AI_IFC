# 工作区域协议（design，被房间/细节设计规范 include）

## 一、工作区域声明

处理每个 zone 时，先声明当前工作区域（zone 定位，防跨 zone 串态）：

```
[工作区域] zone=<zone>, floor=<floor>
```

示例：`[工作区域] zone=tower, floor=tower_std`

## 二、记忆义务在机器

- 当前 zone 的输入已包含全部所需事实（zone 包本层段 + 骨架段）——引用输入里的其他层信息。
- 需要某层信息而输入里没有时，该层在本层不可读，按 `infeasible` 申报处理。

## 三、跨层差异

- 渐退层（diff_from_prev）的差异是机器算好的（见输入片段），你只做选择：
  该内缩的边照做，共享边保持。

## 四、设计范围

- 你的设计空间 = 当前 zone 输入指定的**分区**（骨架分层外推产物：blocks 段/走廊带/大区——
  机器差集已划好，partitions 引用承接）。
- 分区内画分墙是你的本职；分区外（core/corridor/其他 blocks/轮廓）保持原样。
- 分区内装不下 → 返回 `infeasible` 申报（见 references/schemas/rooms.schema.json 的
  infeasible 形态）。
