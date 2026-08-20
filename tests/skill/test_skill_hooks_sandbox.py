"""validate_script 沙箱试跑测试（ifcopenshell 可用时跑）。

拆分自 test_skill_hooks.py（W-0049 文件行数门控），共享常量/夹具从 test_skill_hooks 导入。
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_skill_hooks import (  # noqa: F401
    REPO_ROOT, HOOKS_DIR, SKILL_MD, FLOWS_DIR, HOOK_FILES,
    EVENT_URI_RE, GOOD_SCRIPT, BAD_SCRIPT, MODEL_ID, validate_script,
)
from test_skill_hooks_cli import _run_cli


class TestSandbox:
    """沙箱试跑：有 ifcopenshell 时默认启用；失败即事件。"""

    @pytest.fixture(autouse=True)
    def _skip_without_ifcopenshell(self):
        if importlib.util.find_spec("ifcopenshell") is None:
            pytest.skip("无 ifcopenshell，跳过沙箱测试")

    def test_sandbox_runs_good_script(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["ok"] is True, ev
        assert ev["mode"] == "sandbox"
        assert ev["sandbox"]["ran"] is True
        assert ev["sandbox"]["exit_code"] == 0

    def test_sandbox_runtime_failure_is_event(self, tmp_path):
        src = '''PARAMS = {"a": 1}

def build(params, out_path):
    raise RuntimeError("boom")

if __name__ == "__main__":
    build(PARAMS, "model.ifc")
'''
        p = tmp_path / "script.py"
        p.write_text(src, encoding="utf-8")
        out = _run_cli(p, tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["ok"] is False, ev
        assert ev["uri"] == "aiifc://script/validation-failed"
        assert ev["mode"] == "sandbox"
        assert ev["sandbox"]["exit_code"] != 0
        assert any("沙箱试跑失败" in e for e in ev["errors"])

    def test_static_only_skips_sandbox(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, "--static-only", tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["mode"] == "static"
        assert "sandbox" not in ev

    def test_static_failure_skips_sandbox(self, tmp_path):
        """静态不通过就不试跑（避免在坏脚本上浪费时间）。"""
        p = tmp_path / "script.py"
        p.write_text(BAD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["mode"] == "static"
        assert "sandbox" not in ev

    def test_sandbox_timeout_is_event(self, tmp_path):
        src = '''PARAMS = {"a": 1}

def build(params, out_path):
    import time
    time.sleep(30)

if __name__ == "__main__":
    build(PARAMS, "model.ifc")
'''
        p = tmp_path / "script.py"
        p.write_text(src, encoding="utf-8")
        out = _run_cli(p, "--sandbox-timeout", "1", tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["ok"] is False, ev
        assert ev["mode"] == "sandbox"
        assert ev["sandbox"]["timed_out"] is True

    def test_unreadable_file_is_event_not_crash(self, tmp_path):
        """_validate 阶段文件消失/不可读也产事件，不把 traceback 漏给宿主。

        直接测 _validate（looks_like_build_script 的入口门禁不读不存在文件，
        该守卫防的是「已通过门禁、校验途中文件被移走」的竞态）。
        """
        missing = tmp_path / "gone.py"
        ev = validate_script._validate(
            missing, argparse.Namespace(model_id=None, static_only=True,
                                        sandbox_timeout=60))
        assert ev["uri"] == "aiifc://script/validation-failed"
        assert any("读取脚本失败" in e for e in ev["errors"])

    def test_claude_hook_stdin_path_wins_over_argv(self, tmp_path):
        """stdin 载荷的 file_path 优先于 argv path（真实 Claude Code 调用形态）。"""
        good = tmp_path / "good.py"
        good.write_text(GOOD_SCRIPT, encoding="utf-8")
        bad = tmp_path / "bad.py"
        bad.write_text(BAD_SCRIPT, encoding="utf-8")
        payload = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": str(bad)}})
        out = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "validate_script.py"), str(good),
             "--static-only", "--claude-hook"],
            input=payload, capture_output=True, text=True, timeout=120,
            cwd=str(tmp_path),
        )
        hook = json.loads(out.stdout)
        assert "validation-failed" in hook["additionalContext"]
        assert "good.py" not in hook["additionalContext"]


