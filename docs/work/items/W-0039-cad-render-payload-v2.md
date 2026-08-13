# W-0039: cad render.json（render payload v2：实体带 XDATA key + unsupported 明面化）

- **状态：** done（关闭于 commit 48600ff + 本迭代分支 feat/v0.7-cad-render（PR 待提））
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source，chunk C）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §二「实现路径：前端显示」1 + 「工作项建议」5
- **执行者/分支：** opencode / feat/v0.7-cad-render

## 背景

chunk A（骨架/沙箱）与 chunk B（diff/locate/edit-call）已交付，services/cad 服务端编辑闭环就绪。本项是 chunk C 第一块：前端只读预览的数据源——render payload v2。现 `skills/aidxfv/v1/scripts/dxf/render_payload.py` 的 schema 是无身份 SVG-ish 形态，只能做只读缩略图；v2 升级为实体级 JSON、每个实体带 XDATA 稳定 key（APPID `AIDXF`），前端选中即得 key，为 Phase 2 编辑（locate/edit-call 下钻）打通。对应 spec 决策 3（entity-keyed JSON + Canvas 2D）。

## 涉及位置

- `services/cad/app/render_payload.py`（新增/升级，ezdxf 解析 → 实体级 JSON）
- `services/cad/app/routes_render.py`（新增，`GET /models/{id}/render.json`）
- run/save 发布链路挂接点（镜像 IFC 侧 XKT reconvert 位置：成功后原子更新 render.json）
- 参照：`skills/aidxfv/v1/scripts/dxf/render_payload.py`（schema 思路来源）、`services/ifc` 的转换发布/原子替换模式

## 方案

1. **payload v2 schema**：`GET /models/{id}/render.json` → `{schemaVersion:2, entities:[{key, type, layer, geometry...}], layers:[...], bounds}`；实体 key 取自 XDATA（APPID `AIDXF`），与 ScriptMap 同源。
2. **实体覆盖**：LINE / LWPOLYLINE（bulge 展开为 arc 段）/ CIRCLE / ARC / TEXT / MTEXT / INSERT（块引用展开）。
3. **unsupported 明面化**：白名单外实体列入 `unsupported:[{type, handle, coords}]`，不静默丢（ai-cad-v2-contract 纪律）。
4. **原子更新**：`script/run` 与 `script/save` 成功后重生成 render.json，tmp + `os.replace` 原子发布；失败不污染旧文件。
5. **校验纪律**：业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；`test_verify_isolation` 契约测试继续绿。

**显式范围外：** Go 代理与 kind 分流（W-0040）、web Canvas 查看器组件（后续工作项）、前端编辑下钻（Phase 2，独立 spec）。

## 验收标准

- `GET /models/{id}/render.json` 返回 schemaVersion=2，每个实体带 XDATA key，key 与 ScriptMap 一致。
- LINE/LWPOLYLINE（bulge→arc）/CIRCLE/ARC/TEXT/MTEXT/INSERT 七类实体几何字段正确展开。
- 不支持实体进入 `unsupported` 列表（含 type/handle/coords），不静默丢弃。
- run/save 成功后 render.json 原子更新；重生成失败时旧 render.json 保持可用。
- `cd services/cad && uv run --group dev pytest` 全绿。

## 测试要求

- 契约测试：render.json 实体 key 与 map 一致性（spec「测试要求」render payload 条）。
- 七类实体 golden 用例（含 LWPOLYLINE bulge→arc 展开）；unsupported 实体明面化用例。
- run/save 后 render.json 原子更新用例（含失败不覆盖旧文件）。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
