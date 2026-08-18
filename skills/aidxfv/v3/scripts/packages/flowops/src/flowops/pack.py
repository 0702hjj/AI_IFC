"""flowops/pack.py —— mission 渲染 + state 登记（T42）。

纪律（mission_parrallel §5）：mission = 自包含任务包，一节点一目录。
mission.json 字段对齐 architecture §5 状态机；state.json 是恢复唯一路由。
"""

from __future__ import annotations

import json
from pathlib import Path


def pack_mission(node: str, project_dir: str, inputs: dict,
                 depends_on: list | None = None,
                 worker_type: str = "rooms-worker",
                 prompt_template: str = "prompts/worker/floor_rooms.md",
                 covers: list | None = None,
                 feedback: str | None = None,
                 knowledge: list | None = None) -> dict:
    """渲染一个 mission（<node>/mission.json + prompt.md）。

    :param node: "<zone>.<stage>"（如 podium.rooms）
    :param project_dir: 项目工作目录
    :param inputs: 输入指针集（zone_pack/skeleton_segment/prev_floor_dxf）
    :param knowledge: 注入的设计知识段（push 保底）——[{kind, pain, dsl}]，
        由主 agent 派发前用 goldlib 预筛（pattern 命中段 / case skeleton_dsl）
    :return: mission dict
    """
    project = Path(project_dir)
    mission_dir = project / "missions" / node
    mission_dir.mkdir(parents=True, exist_ok=True)

    mission = {
        "node": node,
        "worker_type": worker_type,
        "covers": covers or [],
        "depends_on": depends_on or [],
        "status": "pending",  # 声明阶段：pending→dispatched→declared→presented→confirmed
        "attempts": 0,
        "inputs": inputs,
        "prompt_template": prompt_template,
    }
    (mission_dir / "mission.json").write_text(
        json.dumps(mission, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # prompt.md：worker 模板渲染（注入输入指针 + knowledge + feedback）
    prompt_lines = [
        f"# {node} mission",
        "",
        "## 输入指针（按需读取，不复制内容）",
    ]
    for key, ptr in inputs.items():
        prompt_lines.append(f"- {key}: `{ptr}`")
    if depends_on:
        prompt_lines.append(f"\n依赖（depends_on）: {', '.join(depends_on)}")
    if knowledge:
        prompt_lines.append("\n## 注入的设计知识（goldlib 预筛，直接套用改参数）")
        for k in knowledge:
            kind = k.get("kind", "pattern")
            pain = k.get("pain", "")
            prompt_lines.append(f"\n--- {kind} 片段（{pain}）---")
            prompt_lines.append(k.get("dsl", ""))
    if feedback:
        prompt_lines.append(f"\n## feedback（重派注入）\n{feedback}")
    prompt_lines.append("\n## 输出契约\n只写本 mission 目录内文件。")
    (mission_dir / "prompt.md").write_text(
        "\n".join(prompt_lines) + "\n", encoding="utf-8")

    return mission


# 回退状态机单处定义（1.3 拍定 2026-08-13）：state.json 是唯一权威——
# steps 引用本表，不各自重复写回退规则。
STATE_MACHINE = {
    "mission": ["pending", "dispatched", "declared", "presented", "confirmed",
                "building", "built", "checked", "done"],
    "skeleton": ["drafting", "checked", "presented", "confirmed"],
    "rollback_rules": [
        {"trigger": "reject_at_breakpoint",
         "action": "redispatch_decl",
         "note": "断点拒绝 → 携 feedback 重派声明（attempts+1，不打扰用户）"},
        {"trigger": "skeleton_level_feedback",
         "action": "rollback_to_step01",
         "note": "骨架级意见 → 回 step-01（唯一全局回滚点，作废未完成 mission）"},
        {"trigger": "schema_fail", "action": "rewrite_decl",
         "note": "validate/normalize SchemaError（exit 2）→ 回喂重发修正声明"},
        {"trigger": "geom_check_fail", "action": "redispatch_with_report",
         "max_attempts": 3, "exceed": "main_agent_takeover",
         "note": "check FAIL → 携报告自动重派；attempts≥3 → 主 agent 亲自接管"},
        {"trigger": "reconcile_fail", "action": "redispatch_with_report",
         "max_attempts": 3, "exceed": "main_agent_takeover",
         "note": "对账 error（画出来≠声明）→ 携报告重派建造"},
        {"trigger": "session_interrupted",
         "action": "resume_from_state",
         "note": "中断恢复 → 读 state.json + 扫 missions/ 对账恢复"},
        {"trigger": "confirmed_floor_edited", "action": "prompt_user",
         "note": "confirmed 层默认不动，提示用户选择"},
    ],
}


def init_state(project_dir: str) -> dict:
    """state.json 初始化（skeleton + missions + presented + 断点位 + 状态机单处定义）。"""
    project = Path(project_dir)
    project.mkdir(parents=True, exist_ok=True)
    state = {
        "skeleton": "drafting",  # 状态词表见 state_machine.skeleton
        "missions": [],
        "presented": [],
        "current_breakpoint": None,
        "state_machine": STATE_MACHINE,  # 单处定义（steps 引用，不重复）
    }
    path = project / "state.json"
    if not path.exists():  # 已有状态不覆盖（幂等）
        path.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def register_mission(node: str, project_dir: str) -> dict:
    """把新 mission 登记进 state.json（不重复）。"""
    project = Path(project_dir)
    state_path = project / "state.json"
    if not state_path.exists():
        init_state(project_dir)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if node not in state["missions"]:
        state["missions"].append(node)
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return state
