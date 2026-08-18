"""floorgeom/io.py —— canon/sha256 确定性写出（T10，V2 layout/io.py 选取）。

纪律：纯函数、字节级确定（sort_keys + 紧凑分隔符 + UTF-8 + 末尾换行）。
同输入同输出，两次写出字节一致。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canon_bytes(payload: dict) -> bytes:
    """dict → 确定性 UTF-8 字节（sort_keys + 紧凑分隔符 + 末尾换行）。"""
    return (json.dumps(payload, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha256_of(payload: dict) -> str:
    """dict → sha256 hex（基于 canon_bytes，同输入同输出）。"""
    return hashlib.sha256(canon_bytes(payload)).hexdigest()


def write_json(payload: dict, path) -> str:
    """确定性写 JSON 文件，返回 sha256。

    :param payload: 可序列化 dict
    :param path: 文件路径（str 或 Path）
    :return: payload 的 sha256 hex
    """
    Path(path).write_bytes(canon_bytes(payload))
    return sha256_of(payload)
