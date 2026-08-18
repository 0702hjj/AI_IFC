"""flowops/orchestrate.py —— 状态编排（补缺 mission / 按产物推进 / 恢复对账）。

边界（2026-08-17 拍定）：包只管**状态记录的正确性**——补缺、合法推进、对账；
**不自动派发 subagent、不自动跑 check/reconcile**。决策（何时派/重派/断点）归
主 agent 原生 agent 协议（dispatch.md）。本模块提供"状态事实"，prompt 提供"决策动作"。

三个纯函数：
- sync_missions:    对照 floors.json#dag.nodes 幂等补缺 mission（包管理可靠性的根基）
- advance_status:   按产物自动推进单 mission 状态（不倒退，不跑检查）
- reconcile_state:  中断恢复全量对账（扫 missions/ 汇总真实状态，不改写）
"""

from __future__ import annotations

import json
from pathlib import Path

from flowops.pack import init_state, pack_mission, register_mission

# 声明段产物 → 状态（按顺序推进，产物越齐状态越靠后）
_DECL_ARTIFACTS = ("rooms.json", "geom.json")
# 建造段产物 → 状态
_BUILD_ARTIFACTS = ("floor.dxf",)
# 封存段产物 → done
_SEAL_ARTIFACTS = ("readback.json", "geom_check.json")


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def sync_missions(project_dir: str, dag: dict | None = None) -> dict:
    """对照 floors.json#dag.nodes 幂等补缺 mission（包管理可靠性的根基）。

    :param dag: 显式 DAG（{nodes:[{node,...}], edges}）；缺省读 derived/floors.json
    :return: {"created": [...], "existing": [...]}
    """
    project = Path(project_dir)
    if dag is None:
        floors = _read_json(project / "derived" / "floors.json") or {}
        dag = floors.get("dag") or {}
    nodes = dag.get("nodes") or []
    init_state(project_dir)
    created, existing = [], []
    for node in nodes:
        node_id = node.get("node")
        if not node_id:
            continue
        mission_dir = project / "missions" / node_id
        if mission_dir.exists():
            existing.append(node_id)
            continue
        pack_mission(node_id, project_dir, inputs={})
        register_mission(node_id, project_dir)
        created.append(node_id)
    return {"created": created, "existing": existing}


def advance_status(project_dir: str, node: str) -> str | None:
    """按产物自动推进单 mission 状态（不倒退，不跑检查）。

    规则（纯产物驱动）：
      rooms.json 存在           → declared
      + geom.json               → presented
      + floor.dxf               → built
      + readback.json + geom_check.json pass → done

    :return: 推进后的状态；node 无 mission 目录 → None
    """
    project = Path(project_dir)
    mission_dir = project / "missions" / node
    mission_path = mission_dir / "mission.json"
    if not mission_path.exists():
        return None
    mission = _read_json(mission_path) or {}

    def has(*names: str) -> bool:
        return all((mission_dir / n).exists() for n in names)

    if has(*_SEAL_ARTIFACTS):
        gc = _read_json(mission_dir / "geom_check.json") or {}
        rec = gc.get("reconcile") or {}
        if rec.get("status") in ("PASS", "PASS_WITH_NOTES") and not rec.get("errors"):
            new = "done"
        else:
            new = "built"
    elif has("floor.dxf"):
        new = "built"
    elif has("geom.json"):
        new = "presented"
    elif has("rooms.json"):
        new = "declared"
    else:
        new = "pending"

    current = mission.get("status", "pending")
    if new != current:
        mission["status"] = new
        mission_path.write_text(
            json.dumps(mission, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return new


def reconcile_state(project_dir: str) -> dict:
    """中断恢复全量对账：扫 missions/ 汇总每个 mission 的真实状态（不改写文件）。

    :return: {node: status}（按 node 排序；缺 mission.json 的目录跳过）
    """
    project = Path(project_dir)
    report = {}
    missions_dir = project / "missions"
    if not missions_dir.exists():
        return report
    for mission_dir in sorted(missions_dir.iterdir()):
        if not mission_dir.is_dir():
            continue
        mission_path = mission_dir / "mission.json"
        if not mission_path.exists():
            continue
        mission = _read_json(mission_path) or {}
        node = mission.get("node") or mission_dir.name
        # 报告"真实状态"：产物 → 状态（不落盘，保守）
        def has(*names: str) -> bool:
            return all((mission_dir / n).exists() for n in names)
        if has(*_SEAL_ARTIFACTS):
            gc = _read_json(mission_dir / "geom_check.json") or {}
            rec = gc.get("reconcile") or {}
            status = "done" if rec.get("status") in ("PASS", "PASS_WITH_NOTES") and not rec.get("errors") else "built"
        elif has("floor.dxf"):
            status = "built"
        elif has("geom.json"):
            status = "presented"
        elif has("rooms.json"):
            status = "declared"
        else:
            status = "pending"
        report[node] = status
    return report
