"""validate_script CLI 静态事件测试（exit code / stdout 事件 URI）。

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


def _run_cli(path, *extra, tmp_path):
    out = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "validate_script.py"), str(path), *extra],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
    )
    return out


class TestCliStaticEvents:
    """CLI 事件输出（--static-only，不依赖 ifcopenshell）。"""

    def test_good_script_event(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, "--static-only", tmp_path=tmp_path)
        assert out.returncode == 0, out.stderr
        ev = json.loads(out.stdout)
        assert ev["uri"] == "aiifc://script/validated"
        assert ev["ok"] is True
        assert ev["mode"] == "static"
        assert ev["errors"] == []

    def test_bad_script_event(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(BAD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, "--static-only", tmp_path=tmp_path)
        assert out.returncode == 1, out.stdout
        ev = json.loads(out.stdout)
        assert ev["uri"] == "aiifc://script/validation-failed"
        assert ev["ok"] is False
        assert any("build" in e for e in ev["errors"])

    def test_model_id_event_uri(self, tmp_path):
        p = tmp_path / f"{MODEL_ID}.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, "--static-only", tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["uri"] == f"aiifc://model/{MODEL_ID}/script/validated"
        assert ev["modelId"] == MODEL_ID

    def test_model_id_cli_override(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        out = _run_cli(p, "--static-only", "--model-id", MODEL_ID, tmp_path=tmp_path)
        ev = json.loads(out.stdout)
        assert ev["uri"] == f"aiifc://model/{MODEL_ID}/script/validated"

    def test_non_build_script_skips(self, tmp_path):
        p = tmp_path / "helper.py"
        p.write_text("x = 1\n", encoding="utf-8")
        out = _run_cli(p, tmp_path=tmp_path)
        assert out.returncode == 0
        ev = json.loads(out.stdout)
        assert ev["mode"] == "skip"
        assert ev["ok"] is True

    def test_claude_hook_output_shape(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(BAD_SCRIPT, encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "validate_script.py"), str(p),
             "--static-only", "--claude-hook"],
            cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
        )
        payload = json.loads(out.stdout)
        assert payload["decision"] == "approve"
        assert "additionalContext" in payload
        assert "aiifc://script/validation-failed" in payload["additionalContext"]
        assert payload["description"]

    def test_claude_hook_skip_non_build(self, tmp_path):
        p = tmp_path / "helper.py"
        p.write_text("x = 1\n", encoding="utf-8")
        out = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "validate_script.py"), str(p), "--claude-hook"],
            cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
        )
        payload = json.loads(out.stdout)
        assert payload == {"decision": "approve"}


