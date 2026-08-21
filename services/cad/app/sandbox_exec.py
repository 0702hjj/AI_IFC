# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""sandbox_exec.py — 沙箱后端探测 + 运行环境/命令构造（从 script_runner 拆出）。

职责：bwrap/rlimit 后端探测（detect_backend / verify_sandbox_backend）、资源限制
（_limits / _nproc_budget）、运行时只读挂载（_runtime_ro_binds）、沙箱环境变量
（_sandbox_env，含共享画法层 drawlib 注入）与 bwrap 命令包装（_sandbox_cmd）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Dict, List

from fastapi import HTTPException

from .config import Settings

# 运行常量由 script_runner 定义（单一源），此处占位由 script_runner 注入——
# 避免拆分后两处常量漂移。script_runner 在 import 本模块后调用 _bind_constants。
RUN_TIMEOUT_S = 60
MEM_LIMIT_BYTES = 1 << 30
MAX_PROCS = 256

_BACKEND: str | None = None


def _bind_constants(run_timeout_s: int, mem_limit_bytes: int, max_procs: int) -> None:
    """由 script_runner 注入运行常量（单一源——script_runner 模块常量）。"""
    global RUN_TIMEOUT_S, MEM_LIMIT_BYTES, MAX_PROCS
    RUN_TIMEOUT_S = run_timeout_s
    MEM_LIMIT_BYTES = mem_limit_bytes
    MAX_PROCS = max_procs


def _limits(nproc: int, fsize: int) -> None:
    """preexec_fn: apply resource limits (inherited by bwrap and its child)."""
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT_S + 30, RUN_TIMEOUT_S + 60))
    resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT_BYTES, MEM_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
    # 单文件写上限：防脚本写满 /data 卷（产物发布前的 product 校验之外的
    # 内核层硬闸，bwrap/rlimit 两后端都生效）。
    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))


def _nproc_budget() -> int:
    """RLIMIT_NPROC 目标值：当前 uid 的 task 数 + MAX_PROCS 余量。"""
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


def _runtime_ro_binds() -> List[str]:
    """运行时按需只读挂载：系统库目录 + 解释器前缀（不含 /data、/etc）。"""
    args: List[str] = []
    seen: set = set()
    for path in ("/usr", "/lib", "/lib64", "/bin", "/sbin",
                 sys.base_prefix, sys.prefix):
        if os.path.isdir(path) and path not in seen:
            seen.add(path)
            args.extend(["--ro-bind", path, path])
    return args


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
                [bwrap, *_runtime_ro_binds(), "--dev", "/dev",
                 "--unshare-net", "--", sys.executable, "-c", "pass"],
                check=True, capture_output=True, timeout=10,
            )
            _BACKEND = "bwrap"
        except (subprocess.SubprocessError, OSError):
            _BACKEND = "rlimit"
    return _BACKEND


def verify_sandbox_backend() -> None:
    """rlimit 降级 fail-closed：bwrap 不可用时拒绝执行，除非显式放行。"""
    if detect_backend() == "bwrap":
        return
    if os.environ.get("ALLOW_RLIMIT_FALLBACK") == "1":
        return
    raise HTTPException(
        status_code=503,
        detail="沙箱后端降级为 rlimit（bwrap 不可用），网络与沙箱外文件系统不隔离；"
        "确认接受降级后设 ALLOW_RLIMIT_FALLBACK=1 显式放行",
    )


def _sandbox_env(settings: Settings, workdir: str) -> Dict[str, str]:
    # PYTHONPATH = flows_dir（cad_script_lib）+ drawlib_dir（archdxf + dxfkit 共享画法层，
    # 冒号分隔多路径）——沙箱脚本可同时 import cad_script_lib（用户编辑线）与
    # dxfkit.draw / archdxf（skill 固化脚本），底层同一套 archdxf。
    pythonpath = settings.flows_dir
    if settings.drawlib_dir:
        pythonpath = pythonpath + ":" + settings.drawlib_dir
    return {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONPATH": pythonpath,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "HOME": workdir,
        "TMPDIR": workdir,
    }


def _sandbox_cmd(settings: Settings, workdir: str) -> List[str]:
    """Wrap the command in bwrap when available (按需挂载 + no network)."""
    if detect_backend() == "bwrap":
        # flows_dir（cad_script_lib）+ drawlib_dir 各路径（archdxf + dxfkit）只读挂载。
        drawlib_binds: List[str] = []
        if settings.drawlib_dir:
            for d in settings.drawlib_dir.split(":"):
                if d and os.path.isdir(d):
                    drawlib_binds += ["--ro-bind", d, d]
        return [
            shutil.which("bwrap") or "bwrap",
            *_runtime_ro_binds(),
            "--ro-bind", settings.flows_dir, settings.flows_dir,
            *drawlib_binds,
            "--tmpfs", "/tmp",
            "--dev", "/dev",
            "--proc", "/proc",
            "--bind", workdir, workdir,
            "--chdir", workdir,
            "--unshare-net",
            "--die-with-parent",
            "--",
        ]
    return []
