# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""script_runner: sandboxed subprocess execution of DXF build scripts.

Mirror of services/ifc test_script_runner.py, adapted for cad: out.dxf
product, ``aidxf-run-*`` sandbox prefix, ``cad_script_lib`` contract gate +
inner-runner ``reset_state()``, ScriptMap envelope publication, and explicit
coverage of both sandbox backends via monkeypatched ``detect_backend``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

from app import script_runner
from app.config import load_settings

GOOD_SCRIPT = '''\
PARAMS = {"name": "t", "width": 6}

def build(params, out_path):
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("0\\nSECTION\\n/* " + params["name"] + " */")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

REAL_DXF_SCRIPT = '''\
import sys

import ezdxf

from cad_script_lib import add_entity, write_and_validate

PARAMS = {"length": 10}

def build(params, out_path):
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    add_entity(msp, "LINE", start=(0, 0), end=(params["length"], 0))
    write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, sys.argv[1])
'''

NO_PARAMS_SCRIPT = '''\
def build(params, out_path):
    open(out_path, "w").write("x")

if __name__ == "__main__":
    import sys
    build({}, sys.argv[1])
'''

NO_BUILD_SCRIPT = '''\
PARAMS = {"a": 1}

if __name__ == "__main__":
    pass
'''

NO_MAIN_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    open(out_path, "w").write("x")
'''

NON_LITERAL_PARAMS_SCRIPT = '''\
import os
PARAMS = {"a": os.environ.get("A")}

def build(params, out_path):
    open(out_path, "w").write("x")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

RUNTIME_ERROR_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    raise RuntimeError("boom-marker")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

INFINITE_LOOP_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    while True:
        pass

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

MEMORY_BOMB_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    blob = b"y" * (4 << 30)
    open(out_path, "wb").write(blob[:1])

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

NO_OUTPUT_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    open("elsewhere.dxf", "w").write("x")  # ignores argv[1]

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

ESCAPE_WRITE_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    open(params["target"], "w").write("pwned")
    open(out_path, "w").write("0\\nSECTION")

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

NOISY_FAILURE_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    import sys
    sys.stderr.write("E" * 10000)
    sys.exit(3)

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''

FORK_LOOP_SCRIPT = '''\
PARAMS = {"a": 1}

def build(params, out_path):
    import os, sys, time
    if os.fork() == 0:
        sys.stderr.write("CHILD:%d\\n" % os.getpid())
        sys.stderr.flush()
        while True:
            time.sleep(1)
    while True:
        time.sleep(1)

if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1])
'''


def _pid_gone(pid: int) -> bool:
    """进程已消失或已僵死（待 reap，等同已死）。"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="ascii") as fh:
            return fh.read().rsplit(") ", 1)[1].split()[0] == "Z"
    except OSError:
        return True


@pytest.fixture()
def settings():
    return load_settings()


class TestContractGate:
    """Static validation rejects non-contract scripts before any execution."""

    @pytest.mark.parametrize(
        "script,marker",
        [
            (NO_PARAMS_SCRIPT, "PARAMS"),
            (NO_BUILD_SCRIPT, "build"),
            (NO_MAIN_SCRIPT, "__main__"),
            (NON_LITERAL_PARAMS_SCRIPT, "字面量"),
            ("PARAMS = {", "语法错误"),
        ],
    )
    def test_contract_violations_422(self, settings, tmp_path: Path, script, marker):
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, script, str(tmp_path / "out.dxf"))
        assert exc.value.status_code == 422
        assert marker in str(exc.value.detail)
        assert not (tmp_path / "out.dxf").exists()

    def test_validate_script_text_reports_errors(self, settings):
        assert script_runner.validate_script_text(settings, GOOD_SCRIPT) == []
        errors = script_runner.validate_script_text(settings, NO_PARAMS_SCRIPT)
        assert any("PARAMS" in e for e in errors)


class TestHappyPath:
    def test_run_writes_out_file_atomically(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        script_runner.run_script(settings, GOOD_SCRIPT, str(out))
        assert out.is_file()
        assert "/* t */" in out.read_text(encoding="utf-8")
        assert not Path(str(out) + ".tmp").exists()

    def test_run_overwrites_existing_out(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        out.write_text("stale", encoding="utf-8")
        script_runner.run_script(settings, GOOD_SCRIPT, str(out))
        assert "stale" not in out.read_text(encoding="utf-8")

    def test_run_real_dxf_build_with_cad_script_lib(self, settings, tmp_path: Path):
        """契约脚本经 PYTHONPATH import cad_script_lib 构建出合法 DXF + XDATA key。"""
        out = tmp_path / "real.dxf"
        script_runner.run_script(settings, REAL_DXF_SCRIPT, str(out))
        assert out.stat().st_size > 0
        import ezdxf

        doc = ezdxf.readfile(str(out))
        lines = doc.modelspace().query("LINE")
        assert len(lines) == 1

    def test_sandbox_temp_dir_cleaned_up(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        script_runner.run_script(settings, GOOD_SCRIPT, str(out))
        leftovers = [
            p for p in Path(script_runner.tempfile.gettempdir()).glob("aidxf-run-*")
        ]
        assert leftovers == []

    def test_rlimit_backend_fallback(self, settings, tmp_path: Path, monkeypatch):
        """bwrap 缺失时的 rlimit 降级路径（monkeypatch detect_backend）。"""
        monkeypatch.setattr(script_runner, "detect_backend", lambda: "rlimit")
        out = tmp_path / "model.dxf"
        script_runner.run_script(settings, REAL_DXF_SCRIPT, str(out))
        assert out.stat().st_size > 0

    def test_bwrap_backend_explicit(self, settings, tmp_path: Path, monkeypatch):
        """bwrap 后端的显式路径（与自动检测解耦，monkeypatch detect_backend）。"""
        if shutil.which("bwrap") is None:
            pytest.skip("bwrap 不可用")
        monkeypatch.setattr(script_runner, "detect_backend", lambda: "bwrap")
        out = tmp_path / "model.dxf"
        script_runner.run_script(settings, GOOD_SCRIPT, str(out))
        assert out.is_file()


class TestMapEnvelope:
    """ScriptMap sidecar → {"scriptHash", "map"} 信封的原子发布/清理。"""

    def test_map_envelope_published_with_script_hash(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        map_dest = tmp_path / "current.map.json"
        script_runner.run_script(
            settings, REAL_DXF_SCRIPT, str(out), map_out=str(map_dest)
        )
        envelope = json.loads(map_dest.read_text(encoding="utf-8"))
        assert envelope["scriptHash"] == script_runner.script_hash(REAL_DXF_SCRIPT)
        entries = envelope["map"]
        # reset_state 后计数从 1 起 → 确定性 key；line 指向用户脚本内的 add_entity 行
        assert "0:line:1" in entries
        assert entries["0:line:1"]["origin"] == "traced"
        assert entries["0:line:1"]["line"] > 0

    def test_missing_sidecar_deletes_stale_map(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        map_dest = tmp_path / "current.map.json"
        script_runner.run_script(
            settings, REAL_DXF_SCRIPT, str(out), map_out=str(map_dest)
        )
        assert map_dest.is_file()
        script_runner.run_script(
            settings, GOOD_SCRIPT, str(out), map_out=str(map_dest)
        )
        assert not map_dest.exists()

    def test_default_map_dest_next_to_out(self, settings, tmp_path: Path):
        out = tmp_path / "model.dxf"
        script_runner.run_script(settings, REAL_DXF_SCRIPT, str(out))
        envelope = json.loads(
            Path(str(out) + ".map.json").read_text(encoding="utf-8")
        )
        assert envelope["scriptHash"] == script_runner.script_hash(REAL_DXF_SCRIPT)


class TestFailureSemantics:
    def test_runtime_error_422_with_stderr(self, settings, tmp_path: Path):
        out = tmp_path / "out.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, RUNTIME_ERROR_SCRIPT, str(out))
        assert exc.value.status_code == 422
        assert "boom-marker" in str(exc.value.detail)
        assert not out.exists()

    def test_stderr_tail_truncated(self, settings, tmp_path: Path):
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(
                settings, NOISY_FAILURE_SCRIPT, str(tmp_path / "out.dxf")
            )
        detail = str(exc.value.detail)
        assert len(detail) < 10000
        assert "E" * 100 in detail  # tail kept

    def test_missing_output_422(self, settings, tmp_path: Path):
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, NO_OUTPUT_SCRIPT, str(tmp_path / "o.dxf"))
        assert exc.value.status_code == 422
        assert "产出" in str(exc.value.detail) or "output" in str(exc.value.detail).lower()


class TestMalicious:
    """死循环 / 超内存 / 越界写，全部被拦截且不产出文件。"""

    def test_infinite_loop_killed_by_timeout(self, settings, tmp_path: Path):
        out = tmp_path / "loop.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, INFINITE_LOOP_SCRIPT, str(out), timeout=2)
        assert exc.value.status_code == 422
        assert "超时" in str(exc.value.detail) or "timeout" in str(exc.value.detail).lower()
        assert not out.exists()

    def test_memory_bomb_killed_by_rlimit(self, settings, tmp_path: Path):
        out = tmp_path / "bomb.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, MEMORY_BOMB_SCRIPT, str(out), timeout=30)
        assert exc.value.status_code == 422
        assert not out.exists()

    @pytest.mark.skipif(
        script_runner.detect_backend() != "bwrap",
        reason="越界写硬拦截需要 bwrap（rlimit 降级模式不拦截 FS 写）",
    )
    def test_write_outside_sandbox_blocked(self, settings, tmp_path: Path):
        target = tmp_path / "evil.txt"
        script = ESCAPE_WRITE_SCRIPT.replace(
            'params["target"]', repr(str(target))
        )
        out = tmp_path / "out.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, script, str(out))
        assert exc.value.status_code == 422
        assert not target.exists()
        assert not out.exists()

    def test_no_network_in_sandbox(self, settings, tmp_path: Path):
        if script_runner.detect_backend() != "bwrap":
            pytest.skip("网络隔离由 bwrap --unshare-net 提供")
        script = GOOD_SCRIPT.replace(
            'fh.write("0\\nSECTION\\n/* " + params["name"] + " */")',
            "import socket\n"
            "        try:\n"
            "            socket.create_connection(('8.8.8.8', 53), timeout=3)\n"
            "            fh.write('NET-OPEN')\n"
            "        except OSError:\n"
            "            fh.write('NET-BLOCKED')",
        )
        out = tmp_path / "net.dxf"
        script_runner.run_script(settings, script, str(out))
        assert out.read_text(encoding="utf-8") == "NET-BLOCKED"


class TestProcessGroupKill:
    """超时必须杀整个进程组（start_new_session + killpg）：脚本 fork 出的
    孙进程不得成孤儿继续跑。"""

    def test_timeout_kills_forked_children(self, settings, tmp_path: Path):
        out = tmp_path / "fork.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, FORK_LOOP_SCRIPT, str(out), timeout=2)
        assert exc.value.status_code == 422
        assert "超时" in str(exc.value.detail)
        assert not out.exists()
        m = re.search(r"CHILD:(\d+)", str(exc.value.detail))
        assert m, f"fork 出的子进程 pid 应随 stderr 截尾带出: {exc.value.detail}"
        child_pid = int(m.group(1))
        # 条件等待 killpg 生效（禁止固定 sleep）
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if _pid_gone(child_pid):
                break
            time.sleep(0.05)
        else:
            pytest.fail(f"forked child {child_pid} survived process-group kill")

    def test_limits_include_nproc(self):
        """preexec 的 rlimits 含 RLIMIT_NPROC（现有 task 数 + MAX_PROCS 余量）。"""
        budget = script_runner._nproc_budget()
        assert budget >= script_runner.MAX_PROCS
        code = (
            "import json, resource, sys\n"
            "sys.stdout.write(json.dumps(resource.getrlimit(resource.RLIMIT_NPROC)))\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            preexec_fn=lambda: script_runner._limits(budget),
            capture_output=True,
            timeout=10,
        )
        assert proc.returncode == 0, proc.stderr
        assert json.loads(proc.stdout) == [budget, budget]

    @pytest.mark.skipif(os.geteuid() == 0, reason="root 可能绕过 RLIMIT_NPROC")
    def test_nproc_budget_blocks_fork_bomb(self, settings, tmp_path: Path):
        """超出余量的 fork 被 RLIMIT_NPROC 拦截 → 422 且不产出文件。"""
        script = GOOD_SCRIPT.replace(
            'fh.write("0\\nSECTION\\n/* " + params["name"] + " */")',
            "import os, time\n"
            f"        for _ in range({script_runner.MAX_PROCS} + 50):\n"
            "            if os.fork() == 0:\n"
            "                time.sleep(5)\n"
            "                os._exit(0)\n"
            "        fh.write('FORKED')",
        )
        out = tmp_path / "bomb.dxf"
        with pytest.raises(HTTPException) as exc:
            script_runner.run_script(settings, script, str(out), timeout=30)
        assert exc.value.status_code == 422
        assert not out.exists()
