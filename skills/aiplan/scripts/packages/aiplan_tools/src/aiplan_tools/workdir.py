"""workdir.py —— projectId → 平台 skill 工作区（{VIEWER_DATA_DIR}/skill-work/{projectID}/aiplan/）。

结构性保证中间产物落盘位置：CLI 内部算 workspace/outdir（不靠 LLM 传对路径）。
平台内使用（agent execute 跑时 env 有 VIEWER_DATA_DIR）；独立使用直传 workspace/--outdir。
边界：CLI（skill）管中间产物落盘（skill-work，CLI 内部算）；tool（agent）管注册/版本化
（deliver_plan → PlanStore）。
"""

from __future__ import annotations

import os


def resolve_aiplan_workdir(project_id: str) -> str:
    """projectId → aiplan 工作区绝对路径（{VIEWER_DATA_DIR}/skill-work/{projectID}/aiplan/）。

    无 VIEWER_DATA_DIR → SystemExit（提示独立使用直传 workspace/--outdir）。
    """
    if not project_id:
        return ""
    data_root = os.environ.get("VIEWER_DATA_DIR", "")
    if not data_root:
        raise SystemExit(
            "VIEWER_DATA_DIR 未设置——--project-id 需平台环境（agent execute 注入）；"
            "独立使用请直传 workspace/--outdir"
        )
    return os.path.join(data_root, "skill-work", project_id, "aiplan")
