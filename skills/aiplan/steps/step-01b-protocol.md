# step-01b 交互协议（P1 设计的协议）

> 本文件是 step-01 渐进设计对话的**协议**：question 工具用法、修改/回退协议、冲突裁决、
> question_templates 用法。轮次内容见 `step-01a-rounds.md`，节奏与回退主干见 `step-01-design.md`。

## question 工具（opencode 原生，主交互通道）

```
question({
  question: "完整问题文本",           // 给用户看的完整问题（无长度限制，可放整段方案）
  header: "简短标签（≤30字）",         // 选择框标题
  options: [                          // 选项列表
    {label: "选项A", description: "说明A"},
    {label: "选项B", description: "说明B"}
  ],
  multiple: false,                    // 多选（可选，默认 false）
  custom: true                        // 允许用户自定义输入（可选，默认看场景）
})
```

**用法铁律**：
- 缺口追问 / 歧义收敛 / 候选拍板 / 方向候选 / 确认 / 获批 → 用 `question` 弹选择框
  （带 options + custom:true）
- 用户自由表达（一段方案描述）→ 直接在对话里听（不弹框，让用户自然说话）
- 轮次回显确认 → 对话里整段复述该轮 + 用 `question` 弹"对吗？对/改"

## 修改与回退协议（改同轮 → 再问同轮；改已锁轮 → 查依赖回退）

用户在某轮说"改 X" → **只更新该轮草案 → 再问同轮**（不重放已锁定轮）：

```
用户: "<修改请求，如改某字段的值>"
你  : （更新该轮草案）
      （对话回显）改好了：<改动后的该项>，其余不变——对吗？
      （不重放其他已锁定轮的内容）
用户: "对"
你  : 该轮锁定 → 进下一轮
```
（回显句式示意：只复述改动项 + "其余不变"，不重复已锁定的其他内容；具体内容按实际修改填写）

**回退（改已锁定轮时）**：
- 改已锁定的轮次 N → 查依赖表（骨架 ← 几何 ← 功能 ← 结构空间）→ 受影响的已锁定轮
  回显变更 + 重问（"因 X 改为 Y，这里按新值重新确认一次"）；未受影响的不打扰
- **换方向**（"要不改成办公吧"）→ 回第 1 轮重走骨架，未锁定轮按新方向重推进

## 冲突裁决（must 级冲突，question 弹裁决）

弹裁决框模板（占位符 `<...>` 按当前冲突的实际情况填写——不内置具体冲突例子）：

```
question({
  question: "<冲突 A 原话> 和 <冲突 B 原话> 打架了——<为什么没法同时满足>。怎么处理？",
  header: "冲突裁决",
  options: [
    {label: "<折中方案 1>", description: "<该方案的具体效果>"},
    {label: "<折中方案 2>", description: "<该方案的具体效果>"},
    {label: "我自己说", description: "自定义解决方案"}
  ],
  custom: true
})
```
用户选 → 记裁决到意图卡片 → 回该轮确认。
冲突的典型类型（朝向 vs 核心筒 / 轮廓 vs 地块 / 屋顶 vs 顶层功能）见
`references/prompts/conflict.md` 的典型冲突表。

## question_templates.json 的用法

`references/question_templates.json` 的 **BRAIN**（方向候选）/ **GAP**（缺口）/ **AMB**（歧义）/
**CAN**（候选）模板**直接喂给 question 工具**：
- 模板的 `options` → question 工具的 options（转成 `{label, description}` 格式）
- 模板的 `问什么/追问语` → question 的 question 文本
- 模板的 `默认` → options 里标出默认项
- 模板的 `轮次归属` → 决定该模板在哪个轮次循环里用
