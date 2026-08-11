"""W-0025: skill hooks 形态/schema/行为测试——「校验即事件」的机器契约。

hooks 是 aiifc skill 包的顶层目录（opencode 插件 + Claude Code 配置 + 校验脚本），
本文件校验：
- bundle 布局与文件存在性（opencode/claude 双形态 + 公共校验脚本）
- schema（opencode 插件含 tool.execute.after 注册；claude 配置 JSON 合法含 PostToolUse）
- validate_script.py 行为（纯 ast 静态校验单测，不依赖 ifcopenshell；
  sandbox 试跑测试在 ifcopenshell 可用时跑）
- 事件 URI 规范化（aiifc://model/{id}/script/validated 形态）
- SKILL.md 文档 hooks 小节 + 降级路径
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "skills" / "aiifc" / "hooks"
SKILL_MD = REPO_ROOT / "skills" / "aiifc" / "SKILL.md"
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"

sys.path.insert(0, str(HOOKS_DIR))
import validate_script  # noqa: E402

HOOK_FILES = (
    "README.md",
    "claude-settings.json",
    "opencode-plugin.ts",
    "validate_script.py",
    "validate_script.sh",
)

EVENT_URI_RE = re.compile(r"^aiifc://(model/m_[0-9a-f]{16}/)?script/(validated|validation-failed)$")

GOOD_SCRIPT = '''PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}

def build(params, out_path):
    pass

if __name__ == "__main__":
    build(PARAMS, "model.ifc")
'''

BAD_SCRIPT = '''PARAMS = {"length": 5.0}

def build(params):
    pass
'''

MODEL_ID = "m_0123456789abcdef"


class TestHooksBundleLayout:
    """hooks 目录是 skill bundle 的一部分：文件齐全 + 双形态 schema 合法。"""

    def test_hooks_files_exist(self):
        for rel in HOOK_FILES:
            assert (HOOKS_DIR / rel).is_file(), f"hooks 缺少 {rel}"

    def test_opencode_plugin_registers_tool_execute_after(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "tool.execute.after" in text, "opencode 插件必须注册 tool.execute.after hook"
        assert "write" in text and "edit" in text, "插件必须监听 write/edit 工具"
        assert "validate_script.py" in text, "插件必须委托给 validate_script.py"

    def test_opencode_plugin_is_typescript_module(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "export default" in text, "插件必须是 opencode 可加载的默认导出模块"

    def test_claude_settings_json_valid_with_posttooluse(self):
        raw = json.loads((HOOKS_DIR / "claude-settings.json").read_text(encoding="utf-8"))
        hooks = raw["hooks"]
        assert "PostToolUse" in hooks, "claude hooks 配置必须含 PostToolUse"
        assert len(hooks["PostToolUse"]) >= 1
        inner = hooks["PostToolUse"][0]
        assert "matcher" in inner
        assert re.search(r"Write|Edit", inner["matcher"]), "matcher 应覆盖 Write/Edit 工具"
        commands = [h["command"] for h in inner["hooks"]]
        assert any("validate_script.sh" in c for c in commands), \
            "PostToolUse 必须指向 validate_script.sh"

    def test_validate_script_sh_is_shell_script(self):
        head = (HOOKS_DIR / "validate_script.sh").read_text(encoding="utf-8").splitlines()
        assert head and head[0].startswith("#!"), "validate_script.sh 必须是可执行脚本"

    def test_hooks_readme_documents_event_uris(self):
        text = (HOOKS_DIR / "README.md").read_text(encoding="utf-8")
        for uri in ("aiifc://model/{id}/script/validated",
                    "aiifc://script/validated",
                    "aiifc://script/validation-failed"):
            assert uri in text, f"hooks README 必须定义事件 URI: {uri}"


class TestOpencodePluginProbe:
    """opencode 插件解释器探测（AIIFC_PYTHON → 仓库 edit-service venv → python3）。

    仓库根不得按固定层级数硬编码（软链安装经 import.meta.url 解析到真实 hooks 目录、
    复制安装则在 .opencode/plugin/ 下——两者深度不同），必须用 AGENTS.md/.git 锚点
    逐级向上定位。见 W-0025 review Finding 1。
    """

    def test_anchor_walk_from_hooks_dir_lands_on_repo_root(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "AGENTS.md" in text and ".git" in text, \
            "插件必须用 AGENTS.md/.git 锚点向上找仓库根"
        root = None
        dir_ = HOOKS_DIR
        for _ in range(8):
            if (dir_ / "AGENTS.md").is_file() or (dir_ / ".git").exists():
                root = dir_
                break
            parent = dir_.parent
            if parent == dir_:
                break
            dir_ = parent
        assert root == REPO_ROOT, \
            f"锚点向上找仓库根落点错误: {root} != {REPO_ROOT}（固定层级会落在仓库父目录）"

    def test_repo_root_not_resolved_by_fixed_levels(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'path.resolve(THIS_DIR, ".."' not in text, \
            "仓库根不得用固定层级数（软链/复制安装深度不同）——必须锚点向上找"

    def test_venv_python_candidate_resolves_under_repo_root(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert '"services", "ifc", ".venv", "bin", "python"' in text, \
            "插件必须构造仓库内 services/ifc venv python 候选路径"
        # 只断言候选路径是仓库根下的相对构造，不断言文件真实存在：
        # CI 的 skill job 用独立 .ci-venv，不创建 services/ifc 的 .venv——
        # 存在性由插件运行时 existsSync 探测决定（缺失时降级 python3），
        # 测试环境不得假设本机开发 venv（2026-08-10 CI flake）。
        candidate = REPO_ROOT / "services" / "ifc" / ".venv" / "bin" / "python"
        assert candidate.parents[2].name == "ifc"
        assert candidate.parents[3].name == "services"
        assert REPO_ROOT in candidate.parents

    def test_probe_chain_order_env_then_venv_then_python3(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "AIIFC_PYTHON" in text
        assert text.index("AIIFC_PYTHON") < text.index('"services", "ifc"') < text.index('"python3"'), \
            "探测链顺序必须 AIIFC_PYTHON → 仓库 venv → python3"


class TestOpencodePluginTimeouts:
    """插件 spawn 超时必须显著大于沙箱超时（W-0025 review Finding 2）。

    否则挂死脚本被插件 SIGTERM 提前掐死，validate_script.py 来不及打印 timed_out
    事件——「失败即事件」退化为静默跳过，且孤儿沙箱子进程残留（TemporaryDirectory
    清理不执行）。
    """

    def test_spawn_timeout_exceeds_sandbox_timeout(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        spawn_ms = re.search(r"SPAWN_TIMEOUT_MS\s*=\s*(\d[\d_]*)", text)
        sandbox_s = re.search(r"SANDBOX_TIMEOUT_S\s*=\s*(\d+)", text)
        assert spawn_ms and sandbox_s, "插件必须定义 SPAWN_TIMEOUT_MS 与 SANDBOX_TIMEOUT_S"
        spawn_ms = int(spawn_ms.group(1).replace("_", ""))
        sandbox_s = int(sandbox_s.group(1))
        assert spawn_ms > sandbox_s * 1000, \
            f"插件超时({spawn_ms}ms)必须大于沙箱超时({sandbox_s}s)"
        assert spawn_ms >= 2 * sandbox_s * 1000, \
            f"插件超时应至少为沙箱超时的 2 倍（当前 {spawn_ms}ms vs {sandbox_s}s）"

    def test_sandbox_timeout_bound_to_constant(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert re.search(r'"--sandbox-timeout",\s*String\(SANDBOX_TIMEOUT_S\)', text), \
            "--sandbox-timeout 必须绑定 SANDBOX_TIMEOUT_S 常量（防两处漂移）"

    def test_timeout_kills_process_group(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "detached" in text, "spawn 必须 detached（独立进程组）"
        assert "process.kill(-proc.pid" in text, "超时必须杀进程组防孤儿沙箱"


class TestOpencodePluginEditTrigger:
    """edit 工具载荷是 {filePath, oldString, newString}（write 才是 {filePath, content}）。

    按工具分支取参；edit 替换区不含契约特征时回读磁盘（替换区外仍可能保留
    PARAMS = / def build(params）。
    """

    def test_edit_reads_newstring(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'tool === "edit"' in text, "必须按工具分支取参"
        assert 'args?.newString' in text, "edit 必须从 args.newString 取内容"

    def test_write_reads_content(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert 'args?.content' in text, "write 必须从 args.content 取内容"

    def test_edit_falls_back_to_disk_content(self):
        text = (HOOKS_DIR / "opencode-plugin.ts").read_text(encoding="utf-8")
        assert "readFileSync" in text, "edit 替换区无契约特征时应回读磁盘文件"


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


class TestSkillMdDocumentsHooks:
    """SKILL.md 必须文档化 hooks：安装/用法 + 事件 URI + 降级路径（hooks 是增强不是替代）。"""

    def test_skill_md_has_hooks_section(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "hooks" in text.lower()
        for marker in ("aiifc://script/validated", "aiifc://script/validation-failed",
                       "validate_script.py", "PostToolUse"):
            assert marker in text, f"SKILL.md hooks 小节缺少 {marker}"

    def test_skill_md_documents_degradation_path(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        assert "MUST #27" in text, "降级路径必须保留 MUST #27 手动校验指引"
        assert "validate_script_contract" in text
