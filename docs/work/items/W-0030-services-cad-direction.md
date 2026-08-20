# W-0030: services/cad 同构方向立项

- **状态：** done
- **优先级：** P2
- **Milestone：** v0.5（可移植复用，本轮仅立项不实施）
- **来源：** spec 2026-08-12-portability-reuse-design.md §5
- **执行者/分支：** kimi-code / docs/close-w0030-w0031
- **关闭说明：** 立项目的已达成——本 item 仅为方向占位（验收标准仅「item 存在且方向写清」），其指向的实施已由 W-0032~W-0045 全部交付（services/cad 骨架/沙箱/REST/diff/locate/edit-call/render.json/Go 代理/web DXF 查看器）。2026-08-20 用户裁决关闭。

## 背景

平台两对等逻辑中，逻辑二「AI 生成 CAD」的 skill 域（aidxfv v1/v2 + aiblueprint-mcp）已交付，但业务逻辑核心 `services/cad` 待建。本轮仅锁定方向、立项占位，不动代码；下迭代作为入口实施。

## 涉及位置

- `services/cad/`（下迭代新建，本轮不碰）
- 下迭代先补独立 spec

## 方案

方向：与 `services/ifc` **完全同构**——
- DXF 生成脚本为唯一事实源（script-as-source）；
- 版本快照；
- 实体级语义 diff；
- REST 编辑 API 同形（PUT /script → run → save → locate）。

下一迭代先补独立 spec，再按 spec 实施。

> 2026-08-12：chunk A（骨架 + 沙箱 + script-as-source REST，W-0032/W-0033）已落地，见 spec 2026-08-12-services-cad-script-as-source-design.md；剩余（locate/edit-call/语义 diff/Go 代理/render.json）按 spec 工作项 3-7 走后续 chunk。
>
> 2026-08-13：chunk B（语义 diff + locate/edit-call，W-0034/W-0035，分支 feat/v0.6-cad-diff）已落地；剩余 spec 工作项 5-7（Go 代理 + MCP、render.json、前端）为后续 chunk。
>
> 2026-08-13：chunk C（render.json payload v2 + Go kind 分流/代理，W-0039/W-0040，分支 feat/v0.7-cad-render）已落地；剩余 spec 工作项 6-7 后半（MCP diff 切换、web Canvas 查看器）为后续 chunk。

## 验收标准

- 本 item 存在且方向写清（本轮验收仅此；实施验收由下迭代 spec 定）。

## 测试要求

- 本轮仅立项，无测试；实施时按下迭代 spec 的测试要求执行（预期与 services/ifc 同级：契约/沙箱/diff 全配测试）。
