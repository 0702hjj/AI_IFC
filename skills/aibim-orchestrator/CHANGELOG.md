# Changelog

## 0.2.0 - 2026-08-12

- 定位修正一：plan 从必经接力锚点降为**可选范式**——设计师带成熟方案时直接派生成子 Agent；仅「从模糊想法起步」才提示 plan 范式，且 plan.json 对齐/草案/确认全部由 cad-agent 的 aidxfv v2 管线内部承载（step-00 → step-04），主 Agent 不再设 plan 确认门禁。强制确认卡点 3 → 2（DXF 确认、IFC 交付确认）。
- 定位修正二：接力信息传递上移主 Agent——子 Agent 之间永不直接交互、互不知道对方；一切产物路径由主 Agent 维护清单并在派发「输入锚点」字段显式传入。RELAY_CONTRACT.md 改定位为「主 Agent 接力手册」（锚点 1 标可选范式），SUBAGENTS.md 子 Agent 输入去掉对 RELAY_CONTRACT 的全局引用。

## 0.1.0 - 2026-08-12

- 首个版本：主 Agent 编排提示词包——意图路由表、子 Agent 分工契约（SUBAGENTS.md）、plan→cad→ifc 接力数据契约（RELAY_CONTRACT.md + plan.sample.json fixture）、opencode 主/子 Agent 配置示例。
- Apache-2.0（主仓 skill；2026-08-13 前为 AGPL-3.0-only）。

## 0.2.1 - 2026-08-13

- 许可证随主仓由 AGPL-3.0-only 改为 Apache-2.0（主仓协议调整，全体贡献者同意）。
