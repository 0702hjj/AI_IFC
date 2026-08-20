"""Local coordinate frames: wall-local and symbol-local mapping.

WallFrame: s runs along the wall from its declared origin, d runs across
the wall thickness (positive inward, d=0 on the outer face). All opening,
symbol, and dimension math happens in (s, d) so callers never write
per-orientation trigonometry.

SymbolFrame: centered at the symbol's placement point, back toward +y at
rotation 0, rotation spins counterclockwise. Primitives draw through the
frame onto a modelspace.

All values are in drawing units; the library is unit-agnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Vec = tuple[float, float]


@dataclass(frozen=True)
class WallFrame:
    origin: Vec
    s_dir: Vec
    d_dir: Vec
    length: float

    def point(self, s: float, d: float) -> Vec:
        return (
            self.origin[0] + s * self.s_dir[0] + d * self.d_dir[0],
            self.origin[1] + s * self.s_dir[1] + d * self.d_dir[1],
        )

    def angle(self, local_degrees: float) -> float:
        radians = math.radians(local_degrees)
        x = math.cos(radians) * self.s_dir[0] + math.sin(radians) * self.d_dir[0]
        y = math.cos(radians) * self.s_dir[1] + math.sin(radians) * self.d_dir[1]
        return math.degrees(math.atan2(y, x)) % 360


def rect_wall_frames(width: float, depth: float) -> dict[str, WallFrame]:
    """Frames for the four exterior walls of a rectangular footprint.

    Building-local coordinates: origin at the footprint's front-left
    corner, x across the width, y toward the rear. Opening offsets on
    front/rear walls measure from the left end; on left/right walls from
    the front end. d is positive toward the interior.
    """

    return {
        "front": WallFrame((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), width),
        "rear": WallFrame((0.0, depth), (1.0, 0.0), (0.0, -1.0), width),
        "left": WallFrame((0.0, 0.0), (0.0, 1.0), (1.0, 0.0), depth),
        "right": WallFrame((width, 0.0), (0.0, 1.0), (-1.0, 0.0), depth),
    }


def partition_frame(
    axis: str, offset: float, thickness: float, length: float
) -> WallFrame:
    """Frame for an interior partition declared as (axis, offset).

    s runs along the axis direction; d=0 sits on the negative-offset face
    so that an "in" swing opens toward the positive side of the cross axis.
    """

    half = thickness / 2
    if axis == "x":
        return WallFrame((0.0, offset - half), (1.0, 0.0), (0.0, 1.0), length)
    if axis == "y":
        return WallFrame((offset - half, 0.0), (0.0, 1.0), (1.0, 0.0), length)
    raise ValueError(f"partition axis must be 'x' or 'y', got {axis!r}")


class SymbolFrame:
    """Draws primitives in symbol-local coords onto a modelspace."""

    def __init__(self, msp, at: Vec, rotation_degrees: float = 0.0, layer: str = "FIXTURE"):
        self.msp = msp
        self.layer = layer
        radians = math.radians(rotation_degrees)
        self._cos = math.cos(radians)
        self._sin = math.sin(radians)
        self._origin = at

    def point(self, x: float, y: float) -> Vec:
        return (
            self._origin[0] + x * self._cos - y * self._sin,
            self._origin[1] + x * self._sin + y * self._cos,
        )

    def rect(self, cx: float, cy: float, w: float, d: float) -> None:
        corners = [
            self.point(cx - w / 2, cy - d / 2),
            self.point(cx + w / 2, cy - d / 2),
            self.point(cx + w / 2, cy + d / 2),
            self.point(cx - w / 2, cy + d / 2),
        ]
        self.msp.add_lwpolyline(corners, close=True, dxfattribs={"layer": self.layer})

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.msp.add_line(self.point(x1, y1), self.point(x2, y2), dxfattribs={"layer": self.layer})

    def circle(self, cx: float, cy: float, radius: float) -> None:
        self.msp.add_circle(center=self.point(cx, cy), radius=radius, dxfattribs={"layer": self.layer})

    def ellipse(self, cx: float, cy: float, rx: float, ry: float) -> None:
        if rx >= ry:
            tip, ratio = (cx + rx, cy), ry / rx
        else:
            tip, ratio = (cx, cy + ry), rx / ry
        center = self.point(cx, cy)
        tip_point = self.point(*tip)
        major = (tip_point[0] - center[0], tip_point[1] - center[1])
        self.msp.add_ellipse(center=center, major_axis=major, ratio=ratio, dxfattribs={"layer": self.layer})

    def label(self, text: str, height: float, cx: float = 0.0, cy: float = 0.0) -> None:
        from ezdxf.enums import TextEntityAlignment

        self.msp.add_text(text, dxfattribs={"layer": self.layer, "height": height}).set_placement(
            self.point(cx, cy), align=TextEntityAlignment.MIDDLE_CENTER
        )
