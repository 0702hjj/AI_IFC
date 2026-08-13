# W-0035: cad locate/edit-call（key→脚本定位 + libcst 标量改写）

- **状态：** done（关闭于「本迭代分支 feat/v0.6-cad-diff（PR 待提）」）
- **优先级：** P1
- **Milestone：** v0.6（services/cad script-as-source，chunk B）
- **来源：** spec 2026-08-12-services-cad-script-as-source-design.md §1.2 端点表 + §三展望 locate 部分 + 「工作项建议」4
- **执行者/分支：** opencode / feat/v0.6-cad-diff

## 背景

chunk A 已交付 ScriptMap 侧车（`v{n}.map.json`：`{key: {line, col, snippet, origin, params_keys}}`，envelope 带 `scriptHash`）。本项是 chunk B 第二块，在 W-0034（语义 diff）之后补齐 web「选中→定位→改写」的服务端两环：locate（key → XDATA → map callsite）与 edit-call（libcst 标量改写）。这是 Phase 2 前端编辑（spec §三展望：Canvas 拖拽命中 key → locate → edit-call）的服务端前提。对应 IFC 侧 `script_edit.py` + locate/edit-call 端点。**门禁：开工需用户确认（CAD 编辑门禁，2026-08-13 用户指示）。**

## 涉及位置

- `services/cad/app/routes_scripts.py`（新增 locate/edit-call 端点，形状镜像 IFC 侧）
- `services/cad/app/script_edit.py`（新增，libcst 标量改写，镜像 `services/ifc/app/script_edit.py`）
- 参照：`services/ifc/tests/test_script_locate.py`、`services/ifc/tests/test_script_edit.py`（测试镜像源）

## 方案

1. **GET /models/{id}/script/locate?key=**：key → 当前 DXF 的 XDATA → map callsite（行/列/snippet/origin/params_keys）；map envelope `scriptHash` 与当前脚本不匹配 → `{found:false, stale:true}` 降级（fail-closed，不猜位置）。
2. **POST /models/{id}/script/edit-call**：libcst 标量改写（仅标量字面量/PARAMS 引用，契约 C-scalar）；stale map → 409 fail-closed；改写目标非 traced callsite → 422；失败路径零副作用（暂存/当前脚本/map 均不变）。仅在 edit-service 直连暴露，不经 Go 代理。
3. **校验纪律**：业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；`test_verify_isolation` 契约测试继续绿。

**显式范围外：** 前端 Canvas 编辑（Phase 2，独立 spec）、Go 代理路由、PARAMS 表单。

## 验收标准

- locate：正确定位 callsite；stale（脚本已变 map 未刷新）降级 `{found:false, stale:true}`，不返回旧位置。
- edit-call：stale map 409 fail-closed；非 traced 目标 422；失败路径零副作用（有专项测试断言文件与暂存链不变）。
- libcst rewrite 单测覆盖（标量字面量改写、PARAMS 引用、拒绝非标量）。
- 端点测试镜像 IFC 侧 `test_script_locate.py` / `test_script_edit.py` 覆盖面。
- `cd services/cad && uv run --group dev pytest` 全绿。

## 测试要求

- **开工需用户确认（CAD 编辑门禁，2026-08-13 用户指示）**——未确认前不得动实现。
- libcst rewrite 单测：标量改写正确性、PARAMS 引用保留、非标量/非 traced 拒绝。
- locate 测试：命中、stale 降级、未知 key。
- edit-call 端点测试：409 stale fail-closed、422 traced、零副作用失败路径（断言暂存/脚本/map 不变）、成功路径改写 + 沙箱试跑 + 暂存一步。
- 新增测试量 ≥ 新增实现量（仓内 ≥1:1 硬规则）。
