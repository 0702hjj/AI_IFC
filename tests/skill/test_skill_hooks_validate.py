"""validate_script 静态校验行为测试（ast 单测，不依赖 ifcopenshell）。

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


class TestLooksLikeBuildScript:
    def _write(self, tmp_path, name, src):
        p = tmp_path / name
        p.write_text(src, encoding="utf-8")
        return p

    def test_py_with_params_marker(self, tmp_path):
        p = self._write(tmp_path, "s.py", 'PARAMS = {"a": 1}\n')
        assert validate_script.looks_like_build_script(p) is True

    def test_py_with_build_marker(self, tmp_path):
        p = self._write(tmp_path, "s.py", "def build(params, out_path):\n    pass\n")
        assert validate_script.looks_like_build_script(p) is True

    def test_py_without_contract_markers(self, tmp_path):
        p = self._write(tmp_path, "s.py", "print('hello')\n")
        assert validate_script.looks_like_build_script(p) is False

    def test_non_py_never_matches(self, tmp_path):
        p = self._write(tmp_path, "s.md", 'PARAMS = {"a": 1}\n')
        assert validate_script.looks_like_build_script(p) is False


class TestExtractModelId:
    """modelId 启发式：路径任一组件（文件名 stem 或祖先目录名）匹配 ^m_[0-9a-f]{16}$。"""

    def test_from_staging_filename(self, tmp_path):
        p = tmp_path / f"{MODEL_ID}.py"
        p.write_text("x\n", encoding="utf-8")
        assert validate_script.extract_model_id(p) == MODEL_ID

    def test_from_models_dir_ancestor(self, tmp_path):
        p = tmp_path / "models" / MODEL_ID / "scripts" / "v1.py"
        p.parent.mkdir(parents=True)
        p.write_text("x\n", encoding="utf-8")
        assert validate_script.extract_model_id(p) == MODEL_ID

    def test_no_model_id(self, tmp_path):
        p = tmp_path / "scripts" / "v1.py"
        p.parent.mkdir(parents=True)
        p.write_text("x\n", encoding="utf-8")
        assert validate_script.extract_model_id(p) is None

    def test_invalid_shape_not_matched(self, tmp_path):
        p = tmp_path / "mx_0123456789abcdef.py"
        p.write_text("x\n", encoding="utf-8")
        assert validate_script.extract_model_id(p) is None


class TestStaticValidate:
    """纯 ast 静态校验（嵌入逻辑，stdlib-only，不 import ifcopenshell）。"""

    def test_good_script_passes(self):
        assert validate_script.static_validate(GOOD_SCRIPT) == []

    def test_missing_build(self):
        errors = validate_script.static_validate('PARAMS = {"a": 1}\n')
        assert any("build" in e for e in errors)

    def test_missing_params(self):
        errors = validate_script.static_validate("def build(params, out_path):\n    pass\n")
        assert any("PARAMS" in e for e in errors)

    def test_params_not_literal(self):
        src = GOOD_SCRIPT.replace('PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                  "PARAMS = dict(length=5.0)")
        errors = validate_script.static_validate(src)
        assert any("字面量" in e for e in errors)

    def test_syntax_error(self):
        errors = validate_script.static_validate("def (:\n")
        assert any("语法错误" in e for e in errors)

    def test_build_signature_too_few_args(self):
        errors = validate_script.static_validate(BAD_SCRIPT)
        assert any("build(params, out_path)" in e for e in errors)

    def test_drift_with_script_lib(self):
        """嵌入静态逻辑必须与 script_lib.validate_script_contract 结论一致（漂移防护）。

        script_lib 不可 import（无 ifcopenshell）时跳过——降级路径正是用嵌入逻辑。
        """
        if importlib.util.find_spec("ifcopenshell") is None:
            pytest.skip("无 ifcopenshell，无法与 script_lib 对照")
        sys.path.insert(0, str(FLOWS_DIR))
        import script_lib
        battery = {
            "good": GOOD_SCRIPT,
            "missing_build": 'PARAMS = {"a": 1}\n\nif __name__ == "__main__":\n    pass\n',
            "bad_signature": BAD_SCRIPT,
            "missing_main": 'PARAMS = {"a": 1}\n\ndef build(params, out_path):\n    pass\n',
            "not_literal": GOOD_SCRIPT.replace('PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                               "PARAMS = dict(length=5.0)"),
            "syntax": "def (:\n",
        }
        for name, src in battery.items():
            p = Path(__file__).parent / "fixtures" / f"_drift_{name}.py"
            p.write_text(src, encoding="utf-8")
            try:
                embedded = validate_script.static_validate(src)
                reference = script_lib.validate_script_contract(p)
            finally:
                p.unlink(missing_ok=True)
            assert sorted(embedded) == sorted(reference), \
                f"嵌入静态校验与 script_lib 结论不一致 ({name}): {embedded} != {reference}"


class TestEventUris:
    def test_uri_regex_matches_generated(self, tmp_path):
        p = tmp_path / f"{MODEL_ID}.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        ev = validate_script.build_event(
            p, errors=[], mode="static", sandbox=None,
            model_id=validate_script.extract_model_id(p))
        assert EVENT_URI_RE.match(ev["uri"]), ev["uri"]
        assert ev["uri"] == f"aiifc://model/{MODEL_ID}/script/validated"

    def test_failed_uri_without_model(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(BAD_SCRIPT, encoding="utf-8")
        ev = validate_script.build_event(
            p, errors=["缺少顶层 build(params, out_path) 入口函数"], mode="static")
        assert ev["uri"] == "aiifc://script/validation-failed"
        assert ev["ok"] is False

    def test_sandbox_detail_carried_in_event(self, tmp_path):
        p = tmp_path / "script.py"
        p.write_text(GOOD_SCRIPT, encoding="utf-8")
        ev = validate_script.build_event(
            p, errors=[], mode="sandbox",
            sandbox={"ran": True, "exit_code": 0, "out_exists": False}, model_id=MODEL_ID)
        assert ev["sandbox"]["exit_code"] == 0
        assert ev["uri"] == f"aiifc://model/{MODEL_ID}/script/validated"


class TestHasBuildEntry:
    def test_present(self):
        assert validate_script.has_build_entry(GOOD_SCRIPT) is True

    def test_absent(self):
        assert validate_script.has_build_entry("PARAMS = {'a': 1}\n") is False

    def test_syntax_error(self):
        assert validate_script.has_build_entry("def (:\n") is False

    def test_async_build_counts(self):
        assert validate_script.has_build_entry(
            "async def build(params, out_path):\n    pass\n") is True


class TestStaticValidateExtra:
    def test_params_not_json_compatible(self):
        src = GOOD_SCRIPT.replace('{"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                  '{("tuple",): 1}')
        errors = validate_script.static_validate(src)
        assert any("JSON-compatible" in e for e in errors)

    def test_missing_main_guard(self):
        src = 'PARAMS = {"a": 1}\n\ndef build(params, out_path):\n    pass\n'
        errors = validate_script.static_validate(src)
        assert any("__main__" in e for e in errors)

    def test_params_expression_rejected(self):
        src = GOOD_SCRIPT.replace('{"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                  "{'a': 1 + 2}")
        errors = validate_script.static_validate(src)
        assert any("字面量" in e for e in errors)


class TestStdlibOnlyContract:
    """validate_script.py 顶部不得 import ifcopenshell——降级路径（无该库也能跑）的机器保证。"""

    def test_no_top_level_ifcopenshell_import(self):
        src = (HOOKS_DIR / "validate_script.py").read_text(encoding="utf-8")
        prelude = src.split("def ", 1)[0]
        assert "import ifcopenshell" not in prelude, \
            "validate_script.py 模块级不得 import ifcopenshell（否则无库环境 import 即崩）"

    def test_importable_without_ifcopenshell(self):
        # 用解释器 -c 在纯净进程验证：只 import 模块不触发 ifcopenshell
        out = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r); import validate_script; "
             "print(validate_script.static_validate('PARAMS = {\"a\": 1}\\n') != [])"
             % str(HOOKS_DIR)],
            capture_output=True, text=True, timeout=60,
        )
        assert out.returncode == 0, out.stderr
        assert out.stdout.strip() == "True"


