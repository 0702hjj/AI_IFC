# P2-9: routes_design.py:56 `__import__("os")` 手误

- **状态：** done
- **关闭于：** 9907f6c
- **优先级：** P2
- **Milestone：** M1（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** opencode / fix/post-v2-audit

## 背景

routes_design.py 第 56 行用 `__import__("os").path.isfile` 而非正常的 `import os`，明显是手误遗留。功能上等价，但可读性差、风格异常，容易被静态检查与读者误解。

## 涉及位置

- `viewer/edit-service/app/routes_design.py:56` — `__import__("os").path.isfile`

## 方案

在文件头正常 `import os`，第 56 行改为 `os.path.isfile(...)`。

## 验收标准

代码中不再出现 `__import__("os")`，行为不变。

## 测试要求

现有 design 路由测试不回归（全绿）。
