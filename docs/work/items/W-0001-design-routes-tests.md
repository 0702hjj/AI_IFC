# W-0001: design.go 全部 11 条路由的 Go 测试

- **状态：** done
- **关闭于：** 5ff8b33（PR #10，随 P0-1 修复同 PR 完成）
- **优先级：** P1
- **Milestone：** M2（见 PLAN-v0.1.0.md）
- **来源：** PLAN-v0.1.0（M2 测试补盲）
- **执行者/分支：** opencode / fix/post-v2-audit

## 背景

`viewer/server/internal/api/design.go` 的 11 条 design 代理路由此前零测试，是 P0-1 契约断裂长期不可见的三大盲区之一。

## 方案

mock edit-service 的 httptest server，断言 Go 输出包 envelope（code/message/data）与错误码映射。

## 验收标准

- design_test.go 覆盖全部 11 条路由 + body 透传 + 404/422/500 错误映射
- `go test ./internal/api/` 全绿

## 测试要求

本项即测试本身；已由 P0-1 的 TDD 流程交付（看红证据见 PR #10 报告）。
