"""Stair plan symbols (scheme level).

One flight = outline + parallel tread lines + diagonal break line +
direction arrow with UP/DN label. Multi-flight stairs are composed by
the caller from mirrored flights plus a landing rectangle.

Local frame: `at` is the flight center, the run points toward +y at
rotation 0 ("up" = ascending toward +y).
"""

from __future__ import annotations

from .frames import SymbolFrame

GOINGS = ("up", "dn")


def draw_stair_flight(
    msp,
    at: tuple[float, float],
    *,
    length: float,
    width: float,
    tread: float = 280.0,
    going: str = "up",
    rotation: float = 0.0,
    layer: str = "STAIR",
    label_height: float = 180.0,
) -> None:
    """Draw one stair flight in plan.

    length = total run (tread x step count); width = flight width;
    going = "up" (arrow points toward +y) or "dn".
    """

    if going not in GOINGS:
        raise ValueError(f"going must be one of {GOINGS}, got {going!r}")
    if length <= 0 or width <= 0 or tread <= 0 or tread > length:
        raise ValueError("require 0 < tread <= length and width > 0")

    sym = SymbolFrame(msp, at, rotation, layer)
    half_l, half_w = length / 2, width / 2

    sym.rect(0, 0, width, length)

    y = -half_l + tread
    while y < half_l - 1e-9:
        sym.line(-half_w, y, half_w, y)
        y += tread

    mid = 0.0
    kink = width * 0.25
    sym.line(-half_w - 0.15 * width, mid - kink, 0.0, mid)
    sym.line(0.0, mid, half_w + 0.15 * width, mid + kink)

    sign = 1.0 if going == "up" else -1.0
    arrow_y0 = -sign * half_l * 0.55
    arrow_y1 = sign * half_l * 0.55
    sym.line(0, arrow_y0, 0, arrow_y1)
    head = width * 0.18
    sym.line(0, arrow_y1, -head * 0.5, arrow_y1 - sign * head)
    sym.line(0, arrow_y1, head * 0.5, arrow_y1 - sign * head)
    sym.label(going.upper(), label_height, 0, arrow_y0 - sign * label_height)


def draw_landing(
    msp,
    at: tuple[float, float],
    *,
    width: float,
    depth: float,
    rotation: float = 0.0,
    layer: str = "STAIR",
) -> None:
    """Stair landing: plain rectangle composed between flights."""

    SymbolFrame(msp, at, rotation, layer).rect(0, 0, width, depth)
