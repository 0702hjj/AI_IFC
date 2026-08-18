"""aiplan 统一 CLI 入口 —— 子命令分组路由（消除 9 个平铺命令的记忆负担）。

分组（2026-08-07 用户拍板：子命令重构 + 文档；2026-08-11 +derive；+intent/normalize P1）：
    aiplan validate <plan|bim|intent> <file>      # 门禁
    aiplan land <plan> <bim> --outdir <dir>        # 成对落盘（run 目录唯一性）
    aiplan canon <file>                            # canon sha256
    aiplan route <workspace>                       # 中断路由
    aiplan geom <check|align> ...  # 几何校验（轮廓 + 跨层对齐）
    aiplan derive --lot ... [--setbacks ...]       # 派生事实（设计依据，P0 迁移）
    aiplan normalize --intent ... --lot ...        # 语义→坐标翻译（P1 迁移）
    aiplan gate <plan>                             # 落盘前设计质量门禁（强制）
    aiplan area <outline> <program> [btype]        # 面积配比
    aiplan pack-drift [packs...]                   # 类型包漂移（维护）

用法：`aiplan <group> <cmd> [args...]` —— 每组路由到对应模块 _main。
旧平铺命令（aiplan-geom 等）保留兼容（console_scripts 不变）。
"""

from __future__ import annotations

import argparse
import sys

from aiplan_tools import area_breakdown
from aiplan_tools import check_pack_drift
from aiplan_tools import derive as derive_mod
from aiplan_tools import design_gate as design_gate_mod
from aiplan_tools import geom
from aiplan_tools import land_pair
from aiplan_tools import normalize as normalize_mod
from aiplan_tools import plan_canon
from aiplan_tools import route as route_mod
from aiplan_tools import translate_golden
from aiplan_tools import validate_bim_supplement
from aiplan_tools import validate_intent
from aiplan_tools import validate_plan

# 分组 → (子命令列表, 默认 _main)
GROUPS: dict[str, dict] = {
    "validate": {"plan": validate_plan, "bim": validate_bim_supplement, "intent": validate_intent},
    "land": {"": land_pair},       # aiplan land <plan> <bim>
    "canon": {"": plan_canon},
    "route": {"": route_mod},
    "geom": {"check": geom, "align": geom},
    "derive": {"": derive_mod},     # aiplan derive --lot ... [--setbacks ...]
    "normalize": {"": normalize_mod},  # aiplan normalize --intent ... --lot ...
    "translate-golden": {"": translate_golden},  # 金例 design_intent → plan.json（D36）
    "gate": {"": design_gate_mod},  # aiplan gate <plan>（落盘前设计质量门禁）
    "area": {"": area_breakdown},
    "pack-drift": {"": check_pack_drift},
}


# 用 argv[1]/argv[2] 取参的模块（area/land——argv[0] 被当脚本名）→ 透传时补占位
# 用 argv[0] 取参的模块（route/pack-drift）与 argparse 类（canon/validate/geom）→ 直接传纯参数
POSITIONAL_FIRST = {area_breakdown, land_pair}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("aiplan 子命令:\n  " + "\n  ".join(sorted(GROUPS)), file=sys.stderr)
        return 2
    group = argv[0]
    if group not in GROUPS:
        print(f"未知组: {group}（可选: {', '.join(sorted(GROUPS))}）", file=sys.stderr)
        return 2
    sub_cmds = GROUPS[group]
    rest = argv[1:]
    # 组内子命令：若 rest[0] 是已知子命令则消费，否则整个 rest 传给默认 _main
    mod = None
    cmd_argv = rest
    if rest and rest[0] in sub_cmds and sub_cmds[rest[0]] is not None:
        mod = sub_cmds[rest[0]]
        if group == "geom":
            # geom 组：子命令名（check/align）由 geom._main 自己解析，
            # 透传时保留（如 `aiplan geom check --outline X` → geom._main(["check","--outline","X"])）
            cmd_argv = rest
        else:
            cmd_argv = rest[1:]
    elif "" in sub_cmds:
        mod = sub_cmds[""]
    else:
        # 组内无默认 → 需显式子命令（如 validate 必须 plan|bim）
        print(f"用法: aiplan {group} <{'|'.join(k for k in sub_cmds if k)}> ...", file=sys.stderr)
        return 2
    # 位置参数模块：补 argv[0] 占位（它们假定 argv[0]=脚本名）
    if mod in POSITIONAL_FIRST:
        cmd_argv = [f"aiplan {group}"] + cmd_argv
    return mod._main(cmd_argv)  # type: ignore[attr-defined]


if __name__ == "__main__":
    sys.exit(main())
