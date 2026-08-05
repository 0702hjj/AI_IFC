# P1-5: PG 测试默认 skip

- **状态：** open
- **优先级：** P1
- **Milestone：** M2（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

`*_pgstore_test.go` 依赖环境变量 `VIEWER_TEST_PG_DSN`，未设置即整体 skip。CI 当前没有 Postgres 服务，因此 PG 存储路径在 CI 中从未运行，File/PG 双存储实现的 parity 没有任何保障——PG 实现可能已悄悄腐化而无人察觉。

## 涉及位置

- `viewer/server/internal/store/*_pgstore_test.go` — 需 `VIEWER_TEST_PG_DSN`，未设即 skip
- `.github/workflows/ci.yml` — server job 无 Postgres service

## 方案

在 ci.yml 的 server job 中加 `services: postgres:16`（带健康检查与端口映射），并将 env `VIEWER_TEST_PG_DSN` 指向该 service，使 `go test ./...` 在 CI 中真实运行 pgstore 测试。

## 验收标准

CI 运行日志中 pgstore 测试显示为 ran 而非 skip，且全部通过。

## 测试要求

本项即测试基建本身；验证方式为 CI 运行输出（pgstore 测试 ran 且绿）。
