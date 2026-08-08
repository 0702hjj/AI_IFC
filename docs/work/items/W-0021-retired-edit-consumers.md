# W-0021: 直改退役残留消费者收口（migrate 端点 + chat notify 编排）

- **状态：** open
- **优先级：** P1
- **Milestone：** v0.2（script-as-source 统一编辑，spec: docs/superpowers/specs/2026-08-08-script-editing-unified-design.md）
- **来源：** feat/script-editing-unified Task 8 任务评审（2026-08-08）

## 背景

L1 直改端点已在 edit-service 退役为 410、Go 代理路由已删（feat/script-editing-unified），但 server 侧仍有两个运行时会失败的残留消费者：

1. **`POST /overrides/migrate`（viewer/server/internal/api/edit.go:393,413）**：内部仍调 `ed.PutEntity` + `ed.Commit` → edit-service 410 → Go 透传 502。更严重的是 `edit_test.go` 的 TestMigrate* 用 fakePy 脚本化 200 响应，**测试在断言真实系统已不可能产生的行为**（假阳性）。
2. **chat notify 三连（viewer/server/internal/api/chat_orchestrator.go:216,220）**：步骤②③仍调已退役端点 → AI 大改落盘编排运行时失败推 `viewer.notify_failed`。

另有小修：edit.go:433 注释引用已删 handler；DELETE /pending docstring 与新定位不符。

## 方案

- migrate 端点：随直改语义一并退役（410/移除 + 前端入口检查），或按 script-as-source 重设计为「override → 脚本修改」——需裁决；无论哪条，fakePy 假阳性测试必须同步修正。
- chat notify 编排：改为 script 管线语义（暂存 → run → save → 重转），移除对已退役端点的调用。
- 顺手：edit.go:433 注释、DELETE /pending docstring、skills 文档残留 `#25-29` 指针（flows/README.md:11、PLAN_DXF_IFC.md、MODELING_WORKFLOWS.md:53）。

## 验收标准

- server 侧无任何对已 410 端点的运行时调用；grep `PutEntity\|edit/entities` 零命中（除退役断言）。
- TestMigrate* 不再脚本化已不可能成功的响应。
- `go test ./...` 绿。

## 测试要求

- chat notify 新编排路径的契约测试（script 暂存→run→save 顺序断言）。
- migrate 退役/重设计的契约测试（410 或新行为）。
