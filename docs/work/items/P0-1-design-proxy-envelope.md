# P0-1: design 代理契约断裂

- **状态：** open
- **优先级：** P0
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

Go 侧 designProxy 把 Python edit-service 返回的原始 JSON 直接透传写出，不包 `{code,message,data}` envelope；而前端 `request()` 强制要求 `env.code === 0`。Python 返回的 JSON 无 `code` 字段，因此所有 `/api/v1/models/{id}/design*` 端点在前端必然 reject，design 相关功能整体不可用。

这是三方测试盲区叠加造成的漏网问题：Go 侧 design.go 全部 11 条路由无任何测试；前端 DesignPanel 测试整体 mock 了 `@/api/client`（DesignPanel.test.tsx:50-59），不触达真实契约；smoke.sh 不覆盖 design 端点。**修复前必须实测验证**（起 Go server + edit-service，curl 一遍 design 端点确认现状）。

## 涉及位置

- `viewer/server/internal/api/design.go:54-63` — designProxy 直接透传裸 JSON，不包 envelope
- `viewer/web/src/api/client.ts:8-13` — `request()` 强制断言 `env.code === 0`
- `viewer/web/src/components/DesignPanel.test.tsx:50-59` — 测试整体 mock client，掩盖契约断裂
- `smoke.sh` — 冒烟脚本不覆盖 design 端点

## 方案

二选一，推荐 (a)：

- **(a) Go 侧 designProxy 包 envelope（推荐）**：在 designProxy 中把 Python 返回的裸 JSON 包装为 `{code: 0, message: "ok", data: <原始 JSON>}` 后写出，与系统其余 API 的 envelope 契约保持一致；Python 侧异常（非 2xx）映射为非零 code 与错误 message。
- **(b) 前端 design 调用走裸 fetch**：前端 design 相关方法绕开 `request()`，直接用裸 fetch 并自行解包。不推荐——破坏前端 API 层的统一契约，后续维护成本高。

## 验收标准

1. 实测起 Go server + edit-service，curl 全 design 端点均返回 envelope 结构且 `code=0`（错误场景返回非零 code）。
2. 前端 DesignPanel 真实联调通过，design 相关操作不再 reject。

## 测试要求

1. Go 侧新增 `design_test.go`，覆盖 design.go 全部 11 条路由：mock editsvc 返回裸 JSON，断言 Go 输出包了 envelope 且字段正确（与 M2 的 W-0001 协同，可同 PR 或紧随其后）。
2. 前端 `client.ts` 的 design 方法加契约测试：mock fetch 返回 envelope，断言解包正确、错误 code 被正确 reject。
