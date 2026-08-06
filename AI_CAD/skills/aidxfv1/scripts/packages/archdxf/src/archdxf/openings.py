"""Opening construction: broken wall runs, jambs, door leaf, window line.

Construction order is fixed: faces -> subtract cuts -> jamb caps -> symbol.
Everything computes in the wall's local frame (see frames.py).
"""

from __future__ import annotations

from .frames import WallFrame
from .intervals import subtract_intervals

SWINGS = ("in-left", "in-right", "out-left", "out-right")


def wall_run(
    msp,
    frame: WallFrame,
    span: tuple[float, float],
    thickness: float,
    cuts: list[tuple[float, float]],
    layer: str,
    *,
    inner_span: tuple[float, float] | None = None,
    poche: bool = True,
    hatch_span: tuple[float, float] | None = None,
) -> None:
    """Draw both faces of a wall run broken at `cuts`, plus solid poché.

    `span` is the outer-face extent; `inner_span` defaults to the span
    shrunk by one thickness at each end (exterior walls stop their inner
    face at the inner corners; pass the same span for partitions).
    `hatch_span` controls fill extent for corner ownership (declare which
    wall owns each corner in the calling package; default = outer span).
    """

    inner = inner_span if inner_span is not None else (
        min(span[0] + thickness, span[1]),
        max(span[1] - thickness, span[0]),
    )
    for face_d, face_span in ((0.0, span), (thickness, inner)):
        for piece_start, piece_end in subtract_intervals(face_span, cuts):
            msp.add_line(
                frame.point(piece_start, face_d),
                frame.point(piece_end, face_d),
                dxfattribs={"layer": layer},
            )
    if poche:
        fill_span = hatch_span if hatch_span is not None else span
        for piece_start, piece_end in subtract_intervals(fill_span, cuts):
            corners = [
                frame.point(piece_start, 0.0),
                frame.point(piece_end, 0.0),
                frame.point(piece_end, thickness),
                frame.point(piece_start, thickness),
            ]
            hatch = msp.add_hatch(dxfattribs={"layer": layer})
            hatch.set_solid_fill()
            hatch.paths.add_polyline_path(corners, is_closed=True)


def jamb_pair(
    msp,
    frame: WallFrame,
    s_start: float,
    width: float,
    thickness: float,
    layer: str,
) -> None:
    """Cap lines across the wall thickness at both ends of an opening."""

    for jamb_s in (s_start, s_start + width):
        msp.add_line(
            frame.point(jamb_s, 0.0),
            frame.point(jamb_s, thickness),
            dxfattribs={"layer": layer},
        )


def door_leaf(
    msp,
    frame: WallFrame,
    s_start: float,
    width: float,
    swing: str,
    wall_thickness: float,
    layer: str = "A-DOOR",
) -> None:
    """Door drawn open 90 degrees: leaf line plus quarter-circle swing arc.

    swing = in/out (which face the leaf rests against; "in" opens toward
    the positive-d side) + left/right (hinge at the lower/higher-s jamb).
    """

    if swing not in SWINGS:
        raise ValueError(f"swing must be one of {SWINGS}, got {swing!r}")
    inward = swing.startswith("in")
    hinge_left = swing.endswith("left")

    face_d = wall_thickness if inward else 0.0
    leaf_sign = 1.0 if inward else -1.0
    hinge_s = s_start if hinge_left else s_start + width

    hinge = frame.point(hinge_s, face_d)
    leaf_tip = frame.point(hinge_s, face_d + leaf_sign * width)
    msp.add_line(hinge, leaf_tip, dxfattribs={"layer": layer})

    strike_angle = frame.angle(0.0 if hinge_left else 180.0)
    leaf_angle = frame.angle(90.0 if inward else 270.0)
    if (leaf_angle - strike_angle) % 360 == 90:
        start_angle, end_angle = strike_angle, leaf_angle
    else:
        start_angle, end_angle = leaf_angle, strike_angle
    msp.add_arc(
        center=hinge,
        radius=width,
        start_angle=start_angle,
        end_angle=end_angle,
        dxfattribs={"layer": layer},
    )


def window_line(
    msp,
    frame: WallFrame,
    s_start: float,
    width: float,
    wall_thickness: float,
    layer: str = "A-GLAZ",
) -> None:
    """Window drawn as a single line centered in the wall thickness."""

    mid = wall_thickness / 2
    msp.add_line(
        frame.point(s_start, mid),
        frame.point(s_start + width, mid),
        dxfattribs={"layer": layer},
    )


def partition_end_cap(
    msp,
    frame: WallFrame,
    s: float,
    thickness: float,
    layer: str,
) -> None:
    """Cap line for a partition end that does not reach another wall."""

    msp.add_line(
        frame.point(s, 0.0),
        frame.point(s, thickness),
        dxfattribs={"layer": layer},
    )
