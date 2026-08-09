# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 0702hjj

"""Sandboxed execution of script-as-source build scripts.

A build script (see skills/aiifc script contract: top-level ``PARAMS`` literal
dict + ``build(params, out_path)`` entry + ``__main__`` guard) is executed as
a subprocess: ``python script.py <out.ifc>`` — the ``__main__`` block passes
``sys.argv[1]`` to ``build``.

Isolation layers:

- **static gate**: ``script_lib.validate_script_contract`` (ast, no execution)
  rejects scripts without PARAMS/build/__main__ before anything runs → 422.
- **bwrap backend** (preferred, auto-detected): read-only root bind +
  writable sandbox cwd + ``--unshare-net`` — writes outside the sandbox fail
  with EROFS and the network is unreachable.
- **rlimit fallback** (no bwrap): same rlimits + isolated cwd/TMPDIR; FS
  writes outside the cwd are *not* blocked (container deployment provides
  that layer — see spec 执行安全).
- both backends: ``RLIMIT_CPU``/``RLIMIT_AS`` + wall-clock timeout, stderr
  tail (2KB) on failure → 422.

The sandbox cwd is a fresh ``aiifc-run-*`` temp dir per run, removed
afterwards. A successful run publishes ``out.ifc`` atomically (tmp +
``os.replace`` in the destination directory).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

from fastapi import HTTPException

from .config import Settings

logger = logging.getLogger(__name__)

RUN_TIMEOUT_S = 60
MEM_LIMIT_BYTES = 1 << 30  # 1 GiB (RLIMIT_AS, virtual address space)
MAX_PROCS = 256  # RLIMIT_NPROC：防 fork 炸弹
STDERR_TAIL_BYTES = 2048

_BACKEND: Optional[str] = None


def script_hash(script_text: str) -> str:
    """sha256 hex of the exact script text — ScriptMap 信封的绑定键。

    发布侧（run_script）把它写进 map 信封；消费侧（locate/edit-call）用它
    比对 staging 当前脚本，不一致即视为 map 过期（行号不可信）。
    """
    return hashlib.sha256(script_text.encode("utf-8")).hexdigest()


def _limits(nproc: int) -> None:
    """preexec_fn: apply resource limits (inherited by bwrap and its child)."""
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT_S + 30, RUN_TIMEOUT_S + 60))
    resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT_BYTES, MEM_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))


def _nproc_budget() -> int:
    """RLIMIT_NPROC 目标值：当前 uid 的 task 数 + MAX_PROCS 余量。

    RLIMIT_NPROC 按 uid 的全部 task（含既有线程）计数，固定上限会让高线程
    环境下的沙箱连 fork/userns 都建不了（EAGAIN）；「现有 + 余量」把脚本
    能新增的进程数约束在 MAX_PROCS 以内，与环境无关。
    """
    uid = os.getuid()
    current = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            if os.stat(f"/proc/{entry}").st_uid != uid:
                continue
            current += len(os.listdir(f"/proc/{entry}/task"))
        except OSError:
            continue
    return current + MAX_PROCS


def detect_backend() -> str:
    """Return "bwrap" when bubblewrap sandboxing works here, else "rlimit"."""
    global _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    _BACKEND = "rlimit"
    bwrap = shutil.which("bwrap")
    if bwrap:
        try:
            subprocess.run(
                [bwrap, "--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev",
                 "--unshare-net", "--", "true"],
                check=True, capture_output=True, timeout=10,
            )
            _BACKEND = "bwrap"
        except (subprocess.SubprocessError, OSError):
            _BACKEND = "rlimit"
    if _BACKEND == "bwrap":
        logger.info("script sandbox backend: bwrap (ro root + unshare-net)")
    else:
        logger.warning(
            "script sandbox backend: rlimit 降级（bwrap 不可用；沙箱外 FS 写与网络不拦截）"
        )
    return _BACKEND


def _load_script_lib(flows_dir: str):
    """Import script_lib from the aiifc flows dir (contract validator)."""
    if flows_dir not in sys.path:
        sys.path.insert(0, flows_dir)
    try:
        import script_lib
    except Exception as exc:  # pragma: no cover - env problem
        raise HTTPException(status_code=500, detail=f"load script_lib: {exc}")
    return script_lib


def validate_script_text(settings: Settings, script_text: str) -> List[str]:
    """Static contract check (ast, no execution). Empty list = passes."""
    script_lib = _load_script_lib(settings.flows_dir)
    with tempfile.TemporaryDirectory(prefix="aiifc-validate-") as workdir:
        path = os.path.join(workdir, "script.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(script_text)
        return script_lib.validate_script_contract(path)


def _sandbox_env(settings: Settings, workdir: str) -> Dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONPATH": settings.flows_dir,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        # BLAS thread pools blow the 1 GiB address-space limit with per-thread
        # stacks; scripts are single-threaded geometry code anyway.
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "HOME": workdir,
        "TMPDIR": workdir,
    }


def _sandbox_cmd(workdir: str) -> List[str]:
    """Wrap the command in bwrap when available (ro root + no network)."""
    if detect_backend() == "bwrap":
        return [
            shutil.which("bwrap") or "bwrap",
            "--ro-bind", "/", "/",
            "--dev-bind", "/dev", "/dev",
            "--bind", workdir, workdir,
            "--chdir", workdir,
            "--unshare-net",
            "--die-with-parent",
            "--",
        ]
    return []


def _tail(data: bytes, limit: int = STDERR_TAIL_BYTES) -> str:
    return data[-limit:].decode("utf-8", errors="replace")


def run_script(
    settings: Settings,
    script_text: str,
    out_path: str,
    *,
    map_out: Optional[str] = None,
    timeout: int = RUN_TIMEOUT_S,
) -> None:
    """Validate + execute script_text, publishing the IFC to out_path.

    The ScriptMap sidecar (``out.ifc.map.json`` from the sandbox) is published
    atomically alongside — wrapped in a ``{"scriptHash", "map"}`` envelope that
    binds the map to the exact script text — to ``map_out`` when given, else
    next to out_path.

    Raises HTTPException(422) on contract violations, timeouts, non-zero
    exits, or a missing/empty product; nothing is written to out_path then.
    """
    errors = validate_script_text(settings, script_text)
    if errors:
        raise HTTPException(
            status_code=422, detail="脚本契约校验失败: " + "; ".join(errors)
        )

    with tempfile.TemporaryDirectory(prefix="aiifc-run-") as workdir:
        script_path = os.path.join(workdir, "script.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script_text)
        tmp_out = os.path.join(workdir, "out.ifc")

        cmd = _sandbox_cmd(workdir) + [sys.executable, script_path, tmp_out]
        nproc = _nproc_budget()  # 在父进程算好，preexec 里不做 /proc 扫描
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            env=_sandbox_env(settings, workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: _limits(nproc),
            start_new_session=True,  # child 成进程组组长，超时杀整组
        )
        try:
            _, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # killpg 杀整个进程组：只杀直接子进程会让脚本 fork 出的孙进程
            # 成孤儿继续跑（M5 终审 I2）。
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
            _, stderr = proc.communicate()
            detail = f"脚本执行超时(>{timeout}s),已终止进程组"
            tail = _tail(stderr)
            if tail:
                detail += ": " + tail
            raise HTTPException(status_code=422, detail=detail)

        if proc.returncode != 0:
            tail = _tail(stderr) or f"exit code {proc.returncode}"
            raise HTTPException(
                status_code=422, detail=f"脚本执行失败(exit {proc.returncode}): {tail}"
            )
        if not os.path.isfile(tmp_out) or os.path.getsize(tmp_out) == 0:
            raise HTTPException(
                status_code=422,
                detail="脚本未产出 IFC(build 必须写入 argv[1] 输出路径)",
            )

        dest_tmp = out_path + ".tmp"
        shutil.copyfile(tmp_out, dest_tmp)
        os.replace(dest_tmp, out_path)

        # ScriptMap sidecar 随产物一并原子发布；本次无 sidecar 时清掉旧文件，
        # 防止上一轮留下的 map 与新产物错位。发布为信封
        # {"scriptHash": sha256(script_text), "map": {...}}——map 行号只对生成
        # 它的那份脚本有效，消费侧按哈希比对 staging 以拒绝过期定位。
        tmp_map = tmp_out + ".map.json"
        map_dest = map_out if map_out is not None else out_path + ".map.json"
        if os.path.isfile(tmp_map):
            try:
                with open(tmp_map, encoding="utf-8") as fh:
                    entries = json.load(fh)
            except (OSError, ValueError):
                raise HTTPException(
                    status_code=422,
                    detail="脚本产出的 map sidecar 不是合法 JSON",
                )
            if not isinstance(entries, dict):
                raise HTTPException(
                    status_code=422,
                    detail="脚本产出的 map sidecar 不是合法 JSON",
                )
            envelope = json.dumps(
                {"scriptHash": script_hash(script_text), "map": entries},
                ensure_ascii=False,
            )
            dest_dir = os.path.dirname(map_dest)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            map_tmp = map_dest + ".tmp"
            with open(map_tmp, "w", encoding="utf-8") as fh:
                fh.write(envelope)
            os.replace(map_tmp, map_dest)
        elif os.path.exists(map_dest):
            os.remove(map_dest)
