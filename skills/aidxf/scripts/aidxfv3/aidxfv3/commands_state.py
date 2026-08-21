# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""aidxfv3 CLI `state` 子命令（sync / advance / reconcile 状态编排）。

从 cli.py 拆出（2026-08-21，500 行门控合规）：只做状态记录，不自动派发
subagent、不自动跑 check/reconcile——决策归主 agent。依赖 flowops.orchestrate。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argparse import Namespace


def cmd_state(args: "Namespace", emit) -> int:
    """state 编排：sync（补缺）/ advance（推进单 mission）/ reconcile（全量对账）。"""
    from flowops.orchestrate import advance_status, reconcile_state, sync_missions

    if not args.project:
        emit({"valid": False, "error": "需 --project"}, args.out)
        return 1
    if args.state_command == "sync":
        result = sync_missions(args.project)
        emit({"valid": True, "created": result["created"],
              "existing": result["existing"]}, args.out)
        return 0
    if args.state_command == "advance":
        if not args.node:
            emit({"valid": False, "error": "advance 需 --node"}, args.out)
            return 1
        status = advance_status(args.project, args.node)
        emit({"valid": True, "node": args.node, "status": status}, args.out)
        return 0
    if args.state_command == "reconcile":
        report = reconcile_state(args.project)
        emit({"valid": True, "missions": report}, args.out)
        return 0
    return 1
