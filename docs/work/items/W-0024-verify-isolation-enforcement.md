# W-0024: verify* 校验隔离的机器强制与存量推开

- **状态：** done（2026-08-10，分支 feat/v0.2-script-closure，commit da02a4f，PR #28）
- **优先级：** P2
- **Milestone：** v0.2（工程契约加固）
- **来源：** 2026-08-08 用户裁决（verify* 方向评估通过，stage_script 样板间可信）

## 背景

AGENTS.md「校验与业务隔离」硬规则已入约（业务规则校验住 `verify*`/`validate*`，handler 只做 decode→verify→领域→翻译；跨路由 helper 单点 `app/route_common.py`），stage_script 已按此重构为样板。当前规则靠 review 自觉，且存量 handler 未收拢。

## 方案

1. **机器强制（核心）**：加契约测试/CI 检查——断言 edit-service 路由文件（`app/routes_*.py`）中 `raise HTTPException` 只出现在 `verify*` 函数与 `route_common.py` 内；Go 侧断言 handler 无内联业务规则 `writeErr`（请求形状校验除外）。grep 级实现即可，放进对应测试套件。
2. **AGENTS.md 补一条**：`verify*` 只做检查（可返回派生数据），禁止副作用/写盘/IO——防止其变成第二个业务层。
3. **存量逐步推开**：不做一次性大改；新代码必须遵守，触碰到的 handler 顺手收拢（W-0021 的 chat_orchestrator / edit.go 重构是首批候选）。

## 验收标准

- 校验隔离契约测试在 CI 运行；故意在 handler 内联 `raise HTTPException` 的提交变红。
- AGENTS.md 副作用禁令入约。
- 存量收拢随各工作项自然发生，不设独立 deadline。

## 测试要求

- 契约测试本身有自证（对一段违规样例代码断言变红）。
