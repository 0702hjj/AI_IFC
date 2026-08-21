"""cli.py --project-id / init 测试（中间产物结构性落 skill-work/{projectID}）。

边界：CLI（skill）管中间产物落盘（skill-work/{projectID}，CLI 内部算）；
tool（agent）管注册平台模型（init_model）+ 方案版本化（deliver_plan/deliver_building）。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = [sys.executable, "-m", "aidxfv3.cli"]


@pytest.fixture()
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "data"
    monkeypatch.setenv("VIEWER_DATA_DIR", str(root))
    return root


def test_init_creates_workdir_and_marker(data_root):
    """init --project-id → 建 skill-work/{projectID}/ + marker（projectId 锚定）。"""
    out = subprocess.run(CLI + ["init", "--project-id", "p_abc"],
                         capture_output=True, text=True, env={**os.environ})
    assert out.returncode == 0, out.stderr
    result = json.loads(out.stdout)
    assert result["valid"] is True
    assert result["projectId"] == "p_abc"
    workdir = Path(result["workdir"])
    assert workdir == data_root / "skill-work" / "p_abc"
    assert workdir.is_dir()
    marker = json.loads((workdir / ".aidxf-work.json").read_text())
    assert marker["projectId"] == "p_abc"


def test_init_requires_project_id(data_root):
    """init 缺 --project-id → 报错（exit 1）。"""
    out = subprocess.run(CLI + ["init"], capture_output=True, text=True,
                         env={**os.environ})
    assert out.returncode == 1
    assert "--project-id" in out.stdout


def test_project_id_resolves_skill_workdir(data_root, monkeypatch):
    """--project-id 内部算 skill-work/{projectID}（覆盖错误 --project，结构性保证）。"""
    from aidxfv3.cli import _apply_project_id, resolve_skill_workdir
    assert resolve_skill_workdir("p_x") == str(data_root / "skill-work" / "p_x")

    class A:
        pass
    a = A()
    a.project_id = "p_x"
    a.project = "/some/wrong/path"  # LLM 传错 --project 也被覆盖
    _apply_project_id(a)
    assert a.project == str(data_root / "skill-work" / "p_x")


def test_project_id_requires_data_dir(monkeypatch):
    """--project-id 但无 VIEWER_DATA_DIR → SystemExit（提示独立使用用 --project）。"""
    monkeypatch.delenv("VIEWER_DATA_DIR", raising=False)
    from aidxfv3.cli import resolve_skill_workdir
    with pytest.raises(SystemExit):
        resolve_skill_workdir("p_x")


def test_project_id_empty_keeps_project(monkeypatch):
    """无 --project-id 时保留 --project 原值（独立使用/显式路径）。"""
    monkeypatch.setenv("VIEWER_DATA_DIR", "/data")
    from aidxfv3.cli import _apply_project_id

    class A:
        pass
    a = A()
    a.project_id = None
    a.project = "/explicit/dir"
    _apply_project_id(a)
    assert a.project == "/explicit/dir"
