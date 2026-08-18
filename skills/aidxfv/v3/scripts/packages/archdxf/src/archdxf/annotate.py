"""Annotation primitives: dimstyle, dimensions, chains, tags, leaders,
labels, symbols.

Dimension text convention is explicit: callers pick mm (plain number) or
feet-inches formatting. All heights/radii are drawing units.
"""

from __future__ import annotations

import math

from ezdxf.enums import TextEntityAlignment

_TEXT_ASPECT = 0.8
DETECTOR_TYPES = ("smoke", "co", "combo")
DETECTOR_LABELS = {"smoke": "S", "co": "CO", "combo": "S/CO"}


def ensure_dimstyle(
    doc,
    name: str = "ARCHDXF",
    *,
    text_height: float,
    arrow_size: float | None = None,
    offset_gap: float | None = None,
) -> None:
    """Create an architectural-tick dimstyle (idempotent).

    Defaults scale from text_height; text sits above the line and reads
    aligned from bottom/right.
    """

    if name in doc.dimstyles:
        return
    arrow = arrow_size if arrow_size is not None else text_height * 0.5
    gap = offset_gap if offset_gap is not None else text_height * 0.25
    doc.dimstyles.new(
        name,
        dxfattribs={
            "dimtxt": text_height,
            "dimasz": arrow,
            "dimexo": gap * 3,
            "dimexe": gap * 1.5,
            "dimgap": gap,
            "dimtad": 1,
            "dimtih": 0,
            "dimtoh": 0,
            "dimdec": 0,
            "dimzin": 8,
            "dimblk": "ARCHTICK",
        },
    )


def format_dim_mm(measurement: float) -> str:
    return f"{measurement:.0f}"


def format_dim_feet_inches(measurement_feet: float) -> str:
    """Feet-inches to the nearest 1/16" (5.8125 -> 5'-9 3/4")."""

    sixteenths = round(measurement_feet * 12 * 16)
    whole_inches, numerator = divmod(sixteenths, 16)
    whole_feet, inches = divmod(whole_inches, 12)
    if numerator:
        divisor = math.gcd(numerator, 16)
        fraction = f" {numerator // divisor}/{16 // divisor}"
    else:
        fraction = ""
    return f"{whole_feet}'-{inches}{fraction}\""


def add_dim(
    msp,
    p1: tuple[float, float],
    p2: tuple[float, float],
    *,
    angle: float,
    base: tuple[float, float],
    dimstyle: str = "ARCHDXF",
    layer: str = "DIM",
    text: str | None = None,
    unit: str = "mm",
) -> None:
    """Linear dimension p1->p2; `base` fixes the dimension line position.

    Text is overridden with the chosen unit convention unless an explicit
    `text` is given.
    """

    radians = math.radians(angle)
    direction = (math.cos(radians), math.sin(radians))
    measurement = abs(
        (p2[0] - p1[0]) * direction[0] + (p2[1] - p1[1]) * direction[1]
    )
    if text is None:
        text = (
            format_dim_mm(measurement)
            if unit == "mm"
            else format_dim_feet_inches(measurement)
        )
    dim = msp.add_linear_dim(
        base=base,
        p1=p1,
        p2=p2,
        angle=angle,
        text=text,
        dimstyle=dimstyle,
        dxfattribs={"layer": layer},
    )
    dim.render()


def dim_chain(
    msp,
    stations: list[float],
    to_point,
    *,
    angle: float,
    base: tuple[float, float],
    dimstyle: str = "ARCHDXF",
    layer: str = "DIM",
    unit: str = "mm",
) -> None:
    """Dimension successive non-zero segments along a station list.

    `to_point(s)` maps a station to a plan point (e.g. frame.point(s, 0)).
    Build opening chains as [corner, jamb, jamb, ..., corner].
    """

    for s0, s1 in zip(stations, stations[1:]):
        if s1 > s0:
            add_dim(
                msp,
                to_point(s0),
                to_point(s1),
                angle=angle,
                base=base,
                dimstyle=dimstyle,
                layer=layer,
                unit=unit,
            )


def add_tag(
    msp,
    mark: str,
    at: tuple[float, float],
    *,
    radius: float,
    text_height: float,
    layer: str = "TEXT",
) -> None:
    """Schedule mark: text in a circle pointing back to a schedule row."""

    msp.add_circle(center=at, radius=radius, dxfattribs={"layer": layer})
    msp.add_text(mark, dxfattribs={"layer": layer, "height": text_height}).set_placement(
        at, align=TextEntityAlignment.MIDDLE_CENTER
    )


def add_leader(
    msp,
    text: str,
    tail: tuple[float, float],
    target: tuple[float, float],
    *,
    height: float,
    layer: str = "TEXT",
    arrow: float | None = None,
) -> None:
    """Label with a leader arrow; text sits at the tail, clear of the target."""

    arrow_len = arrow if arrow is not None else height * 1.6
    dx, dy = target[0] - tail[0], target[1] - tail[1]
    msp.add_line(tail, target, dxfattribs={"layer": layer})
    back = math.atan2(-dy, -dx)
    for wing in (math.radians(20), -math.radians(20)):
        msp.add_line(
            target,
            (
                target[0] + arrow_len * math.cos(back + wing),
                target[1] + arrow_len * math.sin(back + wing),
            ),
            dxfattribs={"layer": layer},
        )
    gap = 0.8 * height
    if abs(dx) >= abs(dy):
        if dx >= 0:
            at, align = (tail[0] - gap, tail[1]), TextEntityAlignment.MIDDLE_RIGHT
        else:
            at, align = (tail[0] + gap, tail[1]), TextEntityAlignment.MIDDLE_LEFT
    elif dy >= 0:
        at, align = (tail[0], tail[1] - gap), TextEntityAlignment.TOP_CENTER
    else:
        at, align = (tail[0], tail[1] + gap), TextEntityAlignment.BOTTOM_CENTER
    msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(at, align=align)


def underlined_text(
    msp,
    text: str,
    at: tuple[float, float],
    *,
    height: float,
    layer: str = "TEXT",
) -> None:
    """Centered text with an underline sized from the font aspect ratio."""

    msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(
        at, align=TextEntityAlignment.MIDDLE_CENTER
    )
    half = len(text) * height * _TEXT_ASPECT / 2
    y = at[1] - 0.7 * height
    msp.add_line((at[0] - half, y), (at[0] + half, y), dxfattribs={"layer": layer})


def room_label(
    msp,
    name: str,
    at: tuple[float, float],
    *,
    height: float,
    area: float | None = None,
    area_text: str | None = None,
    area_height: float | None = None,
    layer: str = "TEXT",
) -> None:
    """Room name: uppercase, underlined, with the stated area beneath."""

    underlined_text(msp, name.upper(), at, height=height, layer=layer)
    if area_text is None and area is not None:
        area_text = f"{area:g} SF"
    if area_text is not None:
        msp.add_text(
            area_text,
            dxfattribs={"layer": layer, "height": area_height or height * 0.67},
        ).set_placement(
            (at[0], at[1] - 1.4 * height), align=TextEntityAlignment.MIDDLE_CENTER
        )


def detector_symbol(
    msp,
    kind: str,
    at: tuple[float, float],
    *,
    radius: float,
    text_height: float,
    layer: str = "FIRE",
) -> None:
    """Smoke/CO alarm: circle with S / CO / S/CO."""

    if kind not in DETECTOR_TYPES:
        raise ValueError(f"detector type must be one of {DETECTOR_TYPES}, got {kind!r}")
    msp.add_circle(center=at, radius=radius, dxfattribs={"layer": layer})
    msp.add_text(
        DETECTOR_LABELS[kind], dxfattribs={"layer": layer, "height": text_height}
    ).set_placement(at, align=TextEntityAlignment.MIDDLE_CENTER)


def view_title(
    msp,
    title: str,
    at: tuple[float, float],
    *,
    height: float,
    scale_label: str | None = None,
    scale_height: float | None = None,
    layer: str = "TEXT",
) -> None:
    """Underlined view title with the print scale written beneath it."""

    underlined_text(msp, title, at, height=height, layer=layer)
    if scale_label is not None:
        msp.add_text(
            f"SCALE: {scale_label}",
            dxfattribs={"layer": layer, "height": scale_height or height * 0.5},
        ).set_placement(
            (at[0], at[1] - 2.0 * height), align=TextEntityAlignment.MIDDLE_CENTER
        )


def north_arrow(
    msp,
    at: tuple[float, float],
    *,
    size: float,
    rotation_degrees: float = 0.0,
    layer: str = "TEXT",
) -> None:
    """North arrow: circle with an N above and a filled pointer.

    `rotation_degrees` turns the arrow counterclockwise from plan-up.
    """

    cx, cy = at
    radius = size / 2
    msp.add_circle(center=at, radius=radius, dxfattribs={"layer": layer})
    radians = math.radians(rotation_degrees)
    ux, uy = -math.sin(radians), math.cos(radians)
    px, py = -uy, ux
    tip = (cx + ux * radius * 0.9, cy + uy * radius * 0.9)
    base_l = (cx + px * radius * 0.25, cy + py * radius * 0.25)
    base_r = (cx - px * radius * 0.25, cy - py * radius * 0.25)
    msp.add_solid([base_l, base_r, tip], dxfattribs={"layer": layer})
    msp.add_text("N", dxfattribs={"layer": layer, "height": size * 0.4}).set_placement(
        (cx + ux * radius * 1.6, cy + uy * radius * 1.6),
        align=TextEntityAlignment.MIDDLE_CENTER,
    )


def section_bubble(
    msp,
    name: str,
    sheet: str,
    center: tuple[float, float],
    direction: tuple[float, float],
    *,
    radius: float,
    text_height: float,
    layer: str = "SECTION",
) -> None:
    """Split section bubble: view letter over destination sheet number,
    plus a filled triangle pointing the view direction."""

    cx, cy = center
    msp.add_circle(center=center, radius=radius, dxfattribs={"layer": layer})
    msp.add_line(
        (cx - radius, cy), (cx + radius, cy), dxfattribs={"layer": layer}
    )
    for text, dy in ((name, 0.45 * radius), (sheet, -0.45 * radius)):
        msp.add_text(text, dxfattribs={"layer": layer, "height": text_height}).set_placement(
            (cx, cy + dy), align=TextEntityAlignment.MIDDLE_CENTER
        )
    ux, uy = direction
    px, py = -uy, ux
    apex = (cx + ux * (radius * 1.8), cy + uy * (radius * 1.8))
    base_1 = (cx + ux * radius * 0.5 + px * radius * 0.7, cy + uy * radius * 0.5 + py * radius * 0.7)
    base_2 = (cx + ux * radius * 0.5 - px * radius * 0.7, cy + uy * radius * 0.5 - py * radius * 0.7)
    msp.add_solid([base_1, base_2, apex], dxfattribs={"layer": layer})
