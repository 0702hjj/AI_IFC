# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2026 0702hjj

"""dxfkit/record.py —— draw 调用序列记录（P0-1：draw_api 不变 + 机器记录 → 固化 build() 脚本）。

定位（draw_api 能力规范不变）：LLM 逐次调 dxfkit.draw 画图时，本模块在 draw 实现侧
记录每次调用的「函数名 + 可序列化参数 + 返回 key」，事后把调用序列固化为 archdxf
环境可运行的 build() 脚本（每 zone 一个，对齐 services/cad script-as-source 契约）。

确定性：draw 的 key 是顺序计数（wall_0001/open_0002/...，reset_keys 归零），同序列
重放产同 key——所以 door/window 等引用 wall_key/open_key 的字面值在重放时自然对齐，
记录字面值即可，无需参数→DSL 反解。

用法（记录）：
    from dxfkit import record
    record.start()                      # 开始记录（reset）
    # ... LLM 逐次调 draw（wall_run/door/window/...，经 record 包装）...
    calls = record.calls()              # 读取调用序列
    script = record.to_build_script(calls, params={...})  # 固化为 build() 脚本

记录开启方式：``start()`` 后调 ``wrap_draw_module(draw_module)`` 把 draw 模块的公共
画图函数就地包装（monkey-patch 模块属性）——LLM 侧代码零改动（draw_api 调用面不变）。
"""

from __future__ import annotations

import functools
import json
from typing import Any, Callable

# 调用序列：[{"fn": 函数名, "args": [可序列化位置参数], "kwargs": {...}, "ret": 返回 key}]
_CALLS: list[dict] = []
# 被包装的画图函数名（draw 模块里逐构件画图、返回 key 的公共函数；不含 new_doc/
# reset_keys/canonicalize 等文档级函数——那些由 build() 骨架负责）。
_DRAW_FNS = (
    "wall_run", "opening", "door", "window", "draw_stair", "draw_landing",
    "draw_fixture", "partition_cap", "draw_dim_chain", "draw_tag", "draw_leader",
    "draw_north_arrow", "draw_title", "draw_section_bubble", "draw_detector",
    "draw_column", "room_label", "draw_partition_base", "draw_rooms_model",
    "draw_windows_from_rooms",
)


def start() -> None:
    """开始记录（清空调用序列）。"""
    _CALLS.clear()


def calls() -> list[dict]:
    """读取已记录的调用序列（只读副本）。"""
    return [dict(c) for c in _CALLS]


def _serializable(value: Any) -> bool:
    """参数可 JSON 序列化（坐标/数值/字符串/列表/dict）——msp 等运行时对象为 False。"""
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


def record_call(fn_name: str, args: tuple, kwargs: dict, ret: Any) -> None:
    """记录一次 draw 调用（排除首参 msp 等不可序列化项）。"""
    ser_args = [a for a in args if _serializable(a)]
    ser_kwargs = {k: v for k, v in kwargs.items() if _serializable(v)}
    _CALLS.append({
        "fn": fn_name,
        "args": ser_args,
        "kwargs": ser_kwargs,
        "ret": ret if _serializable(ret) else None,
    })


def _wrap(fn: Callable, fn_name: str) -> Callable:
    """包装 draw 函数：调用后记录（fn 第一参是 msp，记录时被 _serializable 排除）。"""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        ret = fn(*args, **kwargs)
        record_call(fn_name, args, kwargs, ret)
        return ret
    return wrapper


def wrap_draw_module(draw_module) -> int:
    """把 draw 模块的画图函数就地包装（monkey-patch 模块属性）。返回包装数量。

    LLM 侧代码零改动——draw_api 调用面不变，只是模块属性被换成记录包装版。
    """
    n = 0
    for name in _DRAW_FNS:
        fn = getattr(draw_module, name, None)
        if callable(fn) and not getattr(fn, "_record_wrapped", False):
            wrapped = _wrap(fn, name)
            wrapped._record_wrapped = True  # type: ignore[attr-defined]
            setattr(draw_module, name, wrapped)
            n += 1
    return n


def _render_call(call: dict) -> str:
    """把一条调用记录渲染为 build() 里的一行重放代码（draw.xxx(msp, *args, **kwargs)）。"""
    parts = [repr(a) for a in call["args"]]
    parts += [f"{k}={v!r}" for k, v in call["kwargs"].items()]
    return f"    draw.{call['fn']}(msp, {', '.join(parts)})" if parts else f"    draw.{call['fn']}(msp)"


def to_build_script(calls: list[dict], params: dict | None = None,
                    extra_header: str = "") -> str:
    """把 draw 调用序列固化为 archdxf 环境可运行的 build() 脚本（每 zone 一个）。

    对齐 services/cad script-as-source 契约：顶层 ``PARAMS`` 字面量 dict +
    ``build(params, out_path)`` 入口 + ``__main__`` 守卫。build() 在沙箱 PYTHONPATH
    （archdxf + dxfkit 单一事实源）里 import dxfkit.draw 重放调用序列；出口
    ``doc.saveas``（dxfkit._AsciiDrawing 自动 canonicalize，字节级确定性）。

    :param calls: record.calls() 的调用序列
    :param params: PARAMS 字面量（LLM 声明的 skeleton/rooms/details DSL；缺省空 dict）
    :param extra_header: 脚本头部额外注释（zone 名/溯源）
    :return: 可直接写盘并经 services/cad 沙箱 build 的 Python 源码
    """
    params = params or {}
    params_literal = json.dumps(params, ensure_ascii=False)
    body = "\n".join(_render_call(c) for c in calls)
    header = f"# {extra_header}\n" if extra_header else ""
    return f'''\
{header}PARAMS = {params_literal}

from dxfkit import draw


def build(params, out_path):
    draw.reset_keys()
    doc = draw.new_doc()
    msp = doc.modelspace()
{body}
    doc.saveas(out_path)


if __name__ == "__main__":
    import sys
    build(PARAMS, sys.argv[1] if len(sys.argv) > 1 else "floor.dxf")
'''
