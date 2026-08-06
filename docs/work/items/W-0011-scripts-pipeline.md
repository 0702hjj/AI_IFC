# W-0011: edit-service scripts 管线（staging/save/rollback/沙箱执行）

- **状态：** in-progress
- **优先级：** P0
- **Milestone：** M5 script-as-source
- **来源：** spec 2026-08-06-script-as-source-design.md
- **执行者/分支：** opencode / feat/script-as-source

## 背景

design JSON 管线（regenerate.py + routes_design 的 design 端点）下线，替换为脚本管线：脚本是唯一事实源，staging 存脚本快照，save = 沙箱跑脚本 → 大版本。

## 涉及位置

- `viewer/edit-service/app/`：`script_runner.py`（新）、`design_staging.py`（改脚本快照）、`design_versions.py`（改 script_versions：scripts/v{n}.py + 联动 versions/v{n}.ifc）、`routes_design.py`（端点换脚本语义，可改名 routes_scripts.py）
- 依赖 W-0014 的契约（PARAMS、build(params, out_path)）

## 方案

1. **script_runner.py**：subprocess 跑脚本——`python script.py --out <tmp.ifc>`（或 import 后调 build，subprocess 更安全）；timeout 60s、rlimits（CPU 60s/内存 1GB）、独立临时 cwd、stderr 截尾 2KB；失败 → 422
2. **staging**：复用现 10 步环形缓冲机制，内容从 design JSON 改为脚本文本（含 PARAMS）
3. **save**：staging 当前脚本 → 沙箱跑 → 成功则 scripts/v{n}.py + versions/v{n}.ifc 原子落盘 + 算 v{n-1}↔v{n} diff；失败 → 422 不产生版本
4. **rollback**：取 scripts/v{n}.py 入 staging → 重跑 → uploads/{id}.ifc
5. **端点**（保持 REST 形态，语义换脚本）：`GET/PUT /models/{id}/script`（当前脚本/暂存）、`POST .../script/{undo,redo,discard,save,rollback,run}`、`GET /models/{id}/scripts`（大版本列表）；PARAMS 解析端点 `GET .../script/params`（返回 PARAMS dict 供表单）
6. design JSON 端点下线在本项一并做（routes 删除）；Go 代理 design.go 同步换路径（注意 envelope 契约与 design_test.go 更新）

## 验收标准

- 全流程：PUT 脚本 → run → staging undo/redo → save → versions 列表含 scripts/v{n}.py + versions/v{n}.ifc → rollback 恢复
- 沙箱：恶意/失控脚本（死循环、超内存、写临时目录外）被拦截且不产生版本
- 老模型（无脚本只有 IFC）：script 端点 404/空语义明确，IFC 快照仍可查看
- Go 代理层 envelope 契约测试同步更新（design_test.go → script 路径）

## 测试要求

- TDD 全程；沙箱三恶意用例（死循环/超内存/越界写）必须先红
- staging 落盘恢复（沿用 P1-3 机制）；并发：per-model 锁（补 routes_design 无锁的已知缺口）
- 测试量 ≥ 实现 3 倍（AGENTS.md 纪律）
