# P2-1: pyproject/uv.lock 仍是 simplecadapi 身份

- **状态：** done
- **关闭于：** dbb405c + 15eb800（归档仓 0702hjj/SimpleCADAPI-archive）
- **优先级：** P2
- **Milestone：** M4（见 PLAN-v0.1.0.md）
- **来源：** AUDIT-2026-08-05
- **执行者/分支：** （领取时填）

## 背景

仓库根部的 pyproject.toml、uv.lock、MANIFEST.in 仍是 simplecadapi 2.0.1b1 的包定义，`[project.scripts]` 四个入口指向 src/ 下的 SCAD 遗产代码。当前仓库的实际身份已是 aiifc（IFC 编辑/查看产品），根打包配置与仓库真实身份不符，对使用者和打包工具都具有误导性。

## 涉及位置

- `pyproject.toml` — 仍为 simplecadapi 2.0.1b1 包定义，`[project.scripts]` 四个入口指向 src/
- `uv.lock` — 与上述身份同步的锁文件
- `MANIFEST.in` — SCAD 时代的打包清单
- `src/`、`skills/simplecadapi/` — SCAD 遗产代码本体

## 方案

需用户裁决，三选一（详见 PLAN-v0.1.0.md M4），裁决后执行：

1. **保留归档**：pyproject/uv.lock/MANIFEST 改为 aiifc 身份或直接删除，`src/`、`skills/simplecadapi/` 加归档说明保留。
2. **移出仓库**：`src/`、`skills/simplecadapi/` 拆到独立 repo，主仓瘦身。
3. **彻底删除**：靠 git 历史留存。

## 验收标准

根 pyproject 不再自称 simplecadapi（改身份或文件删除），uv.lock 同步更新。

## 测试要求

若保留打包配置，tests/skill 与 CI skill-pack 不回归（全绿）。
