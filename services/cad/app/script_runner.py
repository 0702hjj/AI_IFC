# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""Sandboxed execution of script-as-source DXF build scripts.

A build script (see skills/aidxfv script contract: top-level ``PARAMS``
literal dict + ``build(params, out_path)`` entry + ``__main__`` guard) is
executed as a subprocess. Unlike services/ifc, the user script is not the
subprocess entry point: an inner runner (``_RUNNER``) imports
``cad_script_lib``, calls ``reset_state()`` (deterministic XDATA key
counters), then executes the user script via ``runpy`` as ``__main__``.

Isolation layers (mirrors services/ifc script_runner):

- **static gate**: ``cad_script_lib.validate_script_contract`` (ast, no
  execution) rejects scripts without PARAMS/build/__main__ → 422.
- **bwrap backend** (preferred, auto-detected): 按需只读挂载（/usr·/lib·
  解释器前缀·flows_dir）+ tmpfs /tmp + 可写 sandbox cwd + ``--unshare-net``
  ——**不挂 /data、不挂 /etc**（整根只读挂载会让脚本读到其他租户的模型，
  W-0047 跨租户读洞）。
- **rlimit fallback** (no bwrap): same rlimits + isolated cwd/TMPDIR; FS
  writes outside the cwd are *not* blocked ——因此 fail-closed：除非显式
  ``ALLOW_RLIMIT_FALLBACK=1``，否则 run 拒绝执行（503）。
- both backends: ``RLIMIT_CPU``/``RLIMIT_AS``/``RLIMIT_NPROC``/
  ``RLIMIT_FSIZE`` + wall-clock timeout with process-group kill；stdout/
  stderr 分块读、累计超上限杀进程组；产物与 map sidecar 发布前大小校验；
  进程级并发闸（满即 429）；stderr tail (2KB) on failure → 422。

The sandbox cwd is a fresh ``aidxf-run-*`` temp dir per run, removed
afterwards. A successful run publishes ``out.dxf`` atomically (tmp +
``os.replace``); the ScriptMap sidecar is published as a
``{"scriptHash", "map"}`` envelope (see ``run_script``).
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
import threading
import time
from typing import Dict, List, Optional

from fastapi import HTTPException

from .config import Settings

logger = logging.getLogger(__name__)

RUN_TIMEOUT_S = 60
MEM_LIMIT_BYTES = 1 << 30  # 1 GiB (RLIMIT_AS, virtual address space)
MAX_PROCS = 256  # RLIMIT_NPROC：防 fork 炸弹
STDERR_TAIL_BYTES = 2048
FSIZE_LIMIT_BYTES = 256 << 20  # RLIMIT_FSIZE 默认（env SCRIPT_MAX_FSIZE_BYTES）
OUTPUT_LIMIT_BYTES = 1 << 20  # stdout+stderr 累计上限（env SCRIPT_MAX_OUTPUT_BYTES）
PRODUCT_LIMIT_BYTES = 256 << 20  # 产物/map 发布上限（env SCRIPT_MAX_PRODUCT_BYTES）
RUN_CONCURRENCY = 3  # run/save 进程级并发闸（env SCRIPT_RUN_CONCURRENCY）

_BACKEND: Optional[str] = None


def _int_env(name: str, default: int) -> int:
    """正整数 env 配置；缺失/非正/非法回退默认。"""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("忽略非法环境变量 %s=%r（回退默认 %d）", name, raw, default)
        return default
    return value if value > 0 else default

_RUNNER = '''\
"""Sandbox inner runner: reset cad_script_lib state, then run the user script."""
import runpy
import sys

import cad_script_lib

cad_script_lib.reset_state()
script_path, out_path = sys.argv[1], sys.argv[2]
sys.argv = [script_path, out_path]
runpy.run_path(script_path, run_name="__main__")
'''


def script_hash(script_text: str) -> str:
    """sha256 hex of the exact script text — ScriptMap 信封的绑定键。

    发布侧（run_script）把它写进 map 信封；消费侧（chunk B 的
    locate/edit-call）用它比对 staging 当前脚本，不一致即视为 map 过期。
    """
    return hashlib.sha256(script_text.encode("utf-8")).hexdigest()


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


def _runtime_ro_binds() -> List[str]:
    """运行时按需只读挂载：系统库目录 + 解释器前缀。

    venv（sys.prefix，site-packages 里的 ezdxf）与 uv/pyenv 管理的解释器
    （sys.base_prefix）常在 /usr 之外，必须显式挂载。按挂载目标路径字面
    去重（**不能**按 realpath：/lib64→usr/lib 这类符号链接若按 realpath
    去重，沙箱里就没有 /lib64 路径，动态加载器直接 ENOENT）。
    **不含 /data、/etc**。
    """
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
    if _BACKEND == "bwrap":
        logger.info("script sandbox backend: bwrap (按需挂载 + unshare-net)")
    else:
        logger.warning(
            "script sandbox backend: rlimit 降级（bwrap 不可用；沙箱外 FS 写与网络不拦截）"
        )
    return _BACKEND


def verify_sandbox_backend() -> None:
    """rlimit 降级 fail-closed：bwrap 不可用时拒绝执行，除非显式放行。

    rlimit 模式不拦截网络与沙箱外 FS 读写（跨租户隔离失效），生产必须跑在
    bwrap 下；本地开发/CI 无 bwrap 时设 ``ALLOW_RLIMIT_FALLBACK=1`` 显式
    接受降级。检查只做判断，无副作用。
    """
    if detect_backend() == "bwrap":
        return
    if os.environ.get("ALLOW_RLIMIT_FALLBACK") == "1":
        return
    raise HTTPException(
        status_code=503,
        detail="沙箱后端降级为 rlimit（bwrap 不可用），网络与沙箱外文件系统不隔离；"
        "确认接受降级后设 ALLOW_RLIMIT_FALLBACK=1 显式放行",
    )


def _load_cad_script_lib(flows_dir: str):
    """Import cad_script_lib from the aidxfv flows dir (contract validator)."""
    if flows_dir not in sys.path:
        sys.path.insert(0, flows_dir)
    try:
        import cad_script_lib
    except Exception as exc:  # pragma: no cover - env problem
        raise HTTPException(status_code=500, detail=f"load cad_script_lib: {exc}")
    return cad_script_lib


def validate_script_text(settings: Settings, script_text: str) -> List[str]:
    """Static contract check (ast, no execution). Empty list = passes."""
    cad_script_lib = _load_cad_script_lib(settings.flows_dir)
    with tempfile.TemporaryDirectory(prefix="aidxf-validate-") as workdir:
        path = os.path.join(workdir, "script.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(script_text)
        return cad_script_lib.validate_script_contract(path)


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


def _sandbox_cmd(settings: Settings, workdir: str) -> List[str]:
    """Wrap the command in bwrap when available (按需挂载 + no network).

    挂载集：系统库/解释器（``_runtime_ro_binds``）+ flows_dir 只读 +
    tmpfs /tmp + 最小 /dev + /proc + 可写 workdir。**不挂 /data、/etc**。
    """
    if detect_backend() == "bwrap":
        return [
            shutil.which("bwrap") or "bwrap",
            *_runtime_ro_binds(),
            "--ro-bind", settings.flows_dir, settings.flows_dir,
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


def _tail(data: bytes, limit: int = STDERR_TAIL_BYTES) -> str:
    return data[-limit:].decode("utf-8", errors="replace")


class _OutputGuard:
    """分块泵 stdout/stderr：累计字节超 cap 置 exceeded（主循环据此杀进程组）。

    替代 ``communicate()`` 全量读入内存：脚本 stdout 泛洪不再撑爆父进程；
    stderr 只留尾（STDERR_TAIL_BYTES）供失败诊断。
    """

    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.total = 0
        self.stderr_tail = bytearray()
        self.lock = threading.Lock()
        self.exceeded = threading.Event()

    def pump(self, stream, *, is_stderr: bool) -> None:
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    return
                with self.lock:
                    self.total += len(chunk)
                    if is_stderr:
                        self.stderr_tail = (
                            self.stderr_tail + chunk
                        )[-STDERR_TAIL_BYTES:]
                    if self.total > self.cap:
                        self.exceeded.set()
        except (OSError, ValueError):  # 进程组被杀后管道关闭
            return


def _kill_group(proc: subprocess.Popen) -> None:
    """killpg 杀整个进程组：只杀直接子进程会让脚本 fork 出的孙进程成孤儿
    继续跑。"""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()


_RUN_GATE: Optional[threading.Semaphore] = None
_RUN_GATE_LOCK = threading.Lock()


def _run_gate() -> threading.Semaphore:
    """进程级 run/save 并发闸（懒初始化；大小 SCRIPT_RUN_CONCURRENCY，默认 3）。

    每次 run 驻留 1 GiB rlimit + 最长 60s 子进程，不设闸会被并发请求拖垮
    整机。测试可 monkeypatch 模块级 ``_RUN_GATE`` 替换闸实例。
    """
    global _RUN_GATE
    with _RUN_GATE_LOCK:
        if _RUN_GATE is None:
            _RUN_GATE = threading.Semaphore(
                _int_env("SCRIPT_RUN_CONCURRENCY", RUN_CONCURRENCY)
            )
        return _RUN_GATE


def run_script(
    settings: Settings,
    script_text: str,
    out_path: str,
    *,
    map_out: Optional[str] = None,
    timeout: int = RUN_TIMEOUT_S,
) -> None:
    """Validate + execute script_text, publishing the DXF to out_path.

    The ScriptMap sidecar (``out.dxf.map.json`` from the sandbox) is published
    atomically alongside — wrapped in a ``{"scriptHash", "map"}`` envelope that
    binds the map to the exact script text — to ``map_out`` when given, else
    next to out_path.

    Raises HTTPException(422) on contract violations, timeouts, non-zero
    exits, or a missing/empty product; nothing is written to out_path then.
    HTTPException(503) when the sandbox degraded to rlimit without an
    explicit ``ALLOW_RLIMIT_FALLBACK=1``; HTTPException(429) when the
    process-wide run gate is full.
    """
    verify_sandbox_backend()
    errors = validate_script_text(settings, script_text)
    if errors:
        raise HTTPException(
            status_code=422, detail="脚本契约校验失败: " + "; ".join(errors)
        )

    gate = _run_gate()
    if not gate.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail="沙箱执行并发已达上限（SCRIPT_RUN_CONCURRENCY），请稍后重试",
        )
    try:
        _run_in_sandbox(settings, script_text, out_path, map_out, timeout)
    finally:
        gate.release()


def _run_in_sandbox(
    settings: Settings,
    script_text: str,
    out_path: str,
    map_out: Optional[str],
    timeout: int,
) -> None:
    """run_script 的落盘+执行+发布主体（并发闸由调用方持有）。"""
    with tempfile.TemporaryDirectory(prefix="aidxf-run-") as workdir:
        script_path = os.path.join(workdir, "script.py")
        with open(script_path, "w", encoding="utf-8") as fh:
            fh.write(script_text)
        runner_path = os.path.join(workdir, "_runner.py")
        with open(runner_path, "w", encoding="utf-8") as fh:
            fh.write(_RUNNER)
        tmp_out = os.path.join(workdir, "out.dxf")

        cmd = _sandbox_cmd(settings, workdir) + [
            sys.executable, runner_path, script_path, tmp_out
        ]
        nproc = _nproc_budget()  # 在父进程算好，preexec 里不做 /proc 扫描
        fsize = _int_env("SCRIPT_MAX_FSIZE_BYTES", FSIZE_LIMIT_BYTES)
        proc = subprocess.Popen(
            cmd,
            cwd=workdir,
            env=_sandbox_env(settings, workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=lambda: _limits(nproc, fsize),
            start_new_session=True,  # child 成进程组组长，超时杀整组
        )
        guard = _OutputGuard(_int_env("SCRIPT_MAX_OUTPUT_BYTES", OUTPUT_LIMIT_BYTES))
        pumps = [
            threading.Thread(
                target=guard.pump, args=(proc.stdout,),
                kwargs={"is_stderr": False}, daemon=True,
            ),
            threading.Thread(
                target=guard.pump, args=(proc.stderr,),
                kwargs={"is_stderr": True}, daemon=True,
            ),
        ]
        for pump in pumps:
            pump.start()
        timed_out = False
        flooded = False
        deadline = time.monotonic() + timeout
        while proc.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            if guard.exceeded.wait(timeout=min(0.05, remaining)):
                flooded = True
                break
        if timed_out or flooded:
            _kill_group(proc)
        proc.wait()
        for pump in pumps:
            pump.join(timeout=5)

        stderr_tail = _tail(bytes(guard.stderr_tail))
        if flooded:
            detail = "脚本输出超过上限,已终止进程组"
            if stderr_tail:
                detail += ": " + stderr_tail
            raise HTTPException(status_code=422, detail=detail)
        if timed_out:
            detail = f"脚本执行超时(>{timeout}s),已终止进程组"
            if stderr_tail:
                detail += ": " + stderr_tail
            raise HTTPException(status_code=422, detail=detail)

        if proc.returncode != 0:
            tail = stderr_tail or f"exit code {proc.returncode}"
            raise HTTPException(
                status_code=422, detail=f"脚本执行失败(exit {proc.returncode}): {tail}"
            )
        if not os.path.isfile(tmp_out) or os.path.getsize(tmp_out) == 0:
            raise HTTPException(
                status_code=422,
                detail="脚本未产出 DXF(build 必须写入 argv[1] 输出路径)",
            )

        # 发布前大小校验：产物与 map sidecar 超限一并拒绝（产物也不落盘，
        # 不留错位产物）。RLIMIT_FSIZE 是内核层硬闸，这里是发布语义层。
        product_limit = _int_env("SCRIPT_MAX_PRODUCT_BYTES", PRODUCT_LIMIT_BYTES)
        if os.path.getsize(tmp_out) > product_limit:
            raise HTTPException(
                status_code=422,
                detail=f"脚本产物超过大小上限({product_limit}B)",
            )
        tmp_map = tmp_out + ".map.json"
        if os.path.isfile(tmp_map) and os.path.getsize(tmp_map) > product_limit:
            raise HTTPException(
                status_code=422,
                detail=f"脚本产出的 map sidecar 超过大小上限({product_limit}B)",
            )

        dest_tmp = out_path + ".tmp"
        shutil.copyfile(tmp_out, dest_tmp)
        os.replace(dest_tmp, out_path)

        # ScriptMap sidecar 随产物一并原子发布；本次无 sidecar 时清掉旧文件，
        # 防止上一轮留下的 map 与新产物错位。发布为信封
        # {"scriptHash": sha256(script_text), "map": {...}}——map 行号只对生成
        # 它的那份脚本有效，消费侧按哈希比对 staging 以拒绝过期定位。
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
