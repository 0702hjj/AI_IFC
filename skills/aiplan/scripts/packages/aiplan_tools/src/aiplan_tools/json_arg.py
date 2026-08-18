"""json_arg —— CLI 参数统一加载（文件路径 或 内联 JSON）。

agent 卡顿根因（2026-08-17）：`geom check --zones` / `area` 只吃内联 JSON，
传 normalize 落盘路径直接 JSONDecodeError；area 也不认 ring 格式。
本模块把「路径优先、内联兼容」收成一处，geom / area / derive 共用。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_arg(s: str) -> Any:
    """解析 CLI 参数为 JSON 对象。

    判定：
    - 空串 → ValueError
    - 以 `[` / `{` 开头 → 当内联 JSON 解析
    - 否则若是已存在文件 → 读文件
    - 否则再尝试当内联 JSON（兼容无花括号的数字等）
    """
    if s is None or str(s).strip() == "":
        raise ValueError("JSON 参数为空")
    text = str(s)
    stripped = text.lstrip()
    if stripped[:1] in "[{":
        return json.loads(text)
    p = Path(text)
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return json.loads(text)


def coerce_lot_points(lot: Any) -> list:
    """把 lot 入参归一成顶点数组 [[x,y],...]。

    接受：
    - 裸数组 `[[0,0],[60000,0],...]`（正式契约）
    - dict 抽 `points` / `lot_polygon_mm` / `coordinates`（容错，防 KeyError: 0）
    """
    if isinstance(lot, dict):
        pts = lot.get("points") or lot.get("lot_polygon_mm") or lot.get("coordinates")
        if pts is None:
            raise ValueError(
                "lot dict 需要 points / lot_polygon_mm / coordinates 键；"
                "正式契约是裸数组 [[x,y],...]"
            )
        return pts
    if isinstance(lot, list):
        return lot
    raise ValueError(f"lot 必须是顶点数组或含 points 的 dict，收到 {type(lot).__name__}")
