"""route —— plan 阶段中断恢复路由（D-4，L-05）。

plan 阶段草案不落盘（D-4），只有 step-02 冻结才写盘。中断恢复靠落盘文件
存在性路由，不依赖会话记忆（对齐架构文档 §4.4 统一加载约定）。

路由规则（run 目录唯一性，2026-08-07 修订；step 编号 2026-08-11 随流程重构
从 P0-P4 改为 P0→P2：step-00 摄取 / step-01 设计 / step-02 交付）：
- plan/ 下**任意 run 目录**（`<时间戳>_<项目>/`）含成对 plan.json + bim_supplement.json
  （结构完整）→ 已冻结，直进 step-02 校验
- 无任何完整 run → 从 step-00 开始（完整 P0→P2）

纯函数，确定性。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _latest_run(workspace: Path) -> Path | None:
    """返回 plan/ 下最新的完整 run 目录（含成对文件且结构完整），无则 None。

    run 目录 = plan/ 下的子目录（时间戳_项目），内含 plan.json + bim_supplement.json。
    """
    plan_root = workspace / "plan"
    if not plan_root.is_dir():
        return None
    candidates = []
    for run_dir in sorted(plan_root.iterdir()):
        if not run_dir.is_dir():
            continue
        plan_file = run_dir / "plan.json"
        bim_file = run_dir / "bim_supplement.json"
        if not (plan_file.exists() and bim_file.exists()):
            continue
        try:
            plan = json.loads(plan_file.read_text(encoding="utf-8"))
            bim = json.loads(bim_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        # 浅校验：bim 的 source_plan_sha256 存在且 plan 有 version 即认为结构完整
        if bim.get("source_plan_sha256") and plan.get("version"):
            candidates.append(run_dir)
    if not candidates:
        return None
    return candidates[-1]  # 字典序最后 = 时间戳最新


def route(workspace: Path) -> str:
    """根据 workspace 下落盘文件状态，返回应走的 step。

    workspace: 工作区根（plan/ 目录在其下）
    返回: "step-00"（从头）或 "step-02"（已冻结，直进校验）
    """
    run = _latest_run(workspace)
    return "step-02" if run is not None else "step-00"


def _main(argv: list[str]) -> int:
    # --project-id <pid>：CLI 内部算 skill-work/{pid}/aiplan/ 为 workspace（结构性落盘根，
    # 优先于显式 workspace 路径）；无 --project-id 时 argv[0] 为 workspace（独立使用）。
    ws = None
    rest = list(argv)
    if "--project-id" in rest:
        i = rest.index("--project-id")
        if i + 1 < len(rest):
            from aiplan_tools.workdir import resolve_aiplan_workdir
            ws = Path(resolve_aiplan_workdir(rest[i + 1]))
            rest = rest[:i] + rest[i + 2:]
    if ws is None:
        ws = Path(rest[0]) if rest else Path.cwd()
    step = route(ws)
    print(step)
    return 0


def main() -> int:
    """console_scripts 无参入口（setuptools 调用）。"""
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
