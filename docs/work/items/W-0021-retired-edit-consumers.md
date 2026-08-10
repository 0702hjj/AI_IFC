# W-0021: 直改退役残留消费者收口（migrate 端点 + chat notify 编排）

- **状态：** done（2026-08-10，分支 feat/v0.2-script-closure，commit deca331/43dca62/33be8f4）
- **优先级：** P1
- **Milestone：** v0.2（script-as-source 统一编辑，spec: docs/superpowers/specs/2026-08-08-script-editing-unified-design.md）
- **来源：** feat/script-editing-unified Task 8 任务评审（2026-08-08）

## 背景

L1 直改端点已在 edit-service 退役为 410、Go 代理路由已删（feat/script-editing-unified），但 server 侧仍有两个运行时会失败的残留消费者：

1. **`POST /overrides/migrate`（viewer/server/internal/api/edit.go:393,413）**：内部仍调 `ed.PutEntity` + `ed.Commit` → edit-service 410 → Go 透传 502。更严重的是 `edit_test.go` 的 TestMigrate* 用 fakePy 脚本化 200 响应，**测试在断言真实系统已不可能产生的行为**（假阳性）。
2. **chat notify 三连（viewer/server/internal/api/chat_orchestrator.go:216,220）**：步骤②③仍调已退役端点 → AI 大改落盘编排运行时失败推 `viewer.notify_failed`。

另有小修：edit.go:433 注释引用已删 handler；DELETE /pending docstring 与新定位不符。

## 方案

- **chat notify 编排：按 Pure Core + Imperative Shell 事件驱动重写**（help.md 架构精要）：编辑动作（暂存/run/save）落盘后由 edit-service/Go server **发事件**，chat orchestrator 作为 Pure Core（Event+State→Action 纯函数，可单测）只消费事件做决策（重转/notify），不主动拉状态、不在 LLM 调用上同步等待。移除对已退役端点的调用。
- migrate 端点：随直改语义一并退役（410/移除 + 前端入口检查），或按 script-as-source 重设计为「override → 脚本修改」——需裁决；无论哪条，fakePy 假阳性测试必须同步修正。
- **减法机会**：直改退役后「三份历史记录并存」（known-limits：Go change log / edit-service edit-history / pending）的写者减少——评估 change log / edit-history 能否归并或下线，至少停写无效字段。
- ~~顺手：skills 文档残留 `#25-29` 指针~~（已于 2026-08-08 随 docs/process-and-subtraction 清扫）；仍含：edit.go:433 注释、DELETE /pending docstring。
- `viewer/scripts/smoke.sh:65-68` 仍打已删的 `PUT /edit/entities/{guid}` + `POST /edit/commit`（edit-service 可达时必挂），需改走 script 管线冒烟；docs/site/development/testing.md:24 的旧链路描述同步。
- Go 死路由清理：`api.go:76`（PUT entities/{entityId}/properties）、`edit.go:40`（overrides/migrate）在册但下游 410——与 migrate 裁决一并处理。

## 验收标准

- server 侧无任何对已 410 端点的运行时调用；grep `PutEntity\|edit/entities` 零命中（除退役断言）。✅
- TestMigrate* 不再脚本化已不可能成功的响应。✅（改为 TestMigrateRouteGone 断言 404）
- `go test ./...` 绿。✅

## 测试要求

- chat notify 新编排路径的契约测试（script 暂存→run→save 顺序断言）。✅（chat_notify_test.go 3 个测试）
- migrate 退役/重设计的契约测试（410 或新行为）。✅

## 落地说明（2026-08-10）

- migrate 裁决：退役（用户已定），路由删除 Go 侧 404；putEntityProperties（override 写路径）保留。
- notify 止血：staging 有脚本 → DELETE pending → PUT /script → run → save → 重转；
  无脚本 → 仅 DELETE pending + 重转。不再写 change log / AISummary 标记（完整 Pure Core
  事件化重写留 W-0017）。
