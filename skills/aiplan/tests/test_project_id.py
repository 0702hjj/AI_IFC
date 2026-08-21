"""aiplan --project-id 测试（route/land 中间产物结构性落 skill-work/{projectID}/aiplan/）。

边界：CLI（skill）管中间产物落盘（skill-work/{pid}/aiplan/，CLI 内部算）；
tool（agent）管注册/版本化（deliver_plan → PlanStore）。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from aiplan_tools.workdir import resolve_aiplan_workdir

CLI = [sys.executable, "-m", "aiplan_tools.cli"]


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setenv("VIEWER_DATA_DIR", str(root))
    return root


def test_resolve_aiplan_workdir(data_root):
    """projectId → {VIEWER_DATA_DIR}/skill-work/{pid}/aiplan/。"""
    assert resolve_aiplan_workdir("p_x") == str(data_root / "skill-work" / "p_x" / "aiplan")


def test_resolve_requires_data_dir(monkeypatch):
    """无 VIEWER_DATA_DIR → SystemExit（提示独立使用直传 workspace/--outdir）。"""
    monkeypatch.delenv("VIEWER_DATA_DIR", raising=False)
    with pytest.raises(SystemExit):
        resolve_aiplan_workdir("p_x")


def test_route_project_id_empty_workdir(data_root):
    """route --project-id（空工作区）→ step-00（从头走完整 P0→P2）。"""
    out = subprocess.run(CLI + ["route", "--project-id", "p_r"],
                         capture_output=True, text=True, env={**os.environ})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "step-00"


def test_route_project_id_uses_skill_workdir(data_root):
    """route --project-id 用 skill-work/{pid}/aiplan/ 为 workspace（plan/ 下判定 run）。"""
    # 造一个完整 run（plan.json 含 version + bim 含 source_plan_sha256）→ route 直进 step-02
    run = data_root / "skill-work" / "p_r2" / "aiplan" / "plan" / "run1"
    run.mkdir(parents=True)
    (run / "plan.json").write_text('{"version": 1}', encoding="utf-8")
    (run / "bim_supplement.json").write_text('{"source_plan_sha256": "abc"}', encoding="utf-8")
    out = subprocess.run(CLI + ["route", "--project-id", "p_r2"],
                         capture_output=True, text=True, env={**os.environ})
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "step-02"  # 有完整 run → 直进 step-02
