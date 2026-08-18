"""Fixture and appliance symbols.

Standard footprints below are metric (millimetre) industry sizes; scale
proportionally when drawing in other unit systems. Each symbol draws in a
local frame centered at `at` with its back toward +y at rotation 0.
"""

from __future__ import annotations

from .frames import SymbolFrame

FIXTURE_TYPES = (
    "toilet",
    "lavatory",
    "bathtub",
    "shower",
    "kitchen-sink",
    "range",
    "refrigerator",
    "washer-dryer",
    "water-heater",
    "counter",
)


def draw_fixture(
    msp,
    kind: str,
    at: tuple[float, float],
    rotation: float = 0.0,
    size: tuple[float, float] | None = None,
    layer: str = "FIXTURE",
    label_height: float = 180.0,
) -> None:
    """Draw a fixture symbol of the given type at `at`.

    `size` is required for "counter" (no standard footprint) and rejected
    for every other type.
    """

    if kind not in FIXTURE_TYPES:
        raise ValueError(f"fixture type must be one of {FIXTURE_TYPES}, got {kind!r}")
    if kind == "counter" and size is None:
        raise ValueError("counter requires an explicit size (width, depth)")
    if kind != "counter" and size is not None:
        raise ValueError(f"{kind} has a standard footprint; do not set size")

    sym = SymbolFrame(msp, at, rotation, layer)

    if kind == "toilet":
        sym.rect(0, 265, 400, 170)
        sym.ellipse(0, -95, 200, 265)
    elif kind == "lavatory":
        sym.ellipse(0, 0, 275, 225)
    elif kind == "bathtub":
        sym.rect(0, 0, 1700, 750)
        sym.rect(0, 0, 1540, 590)
        sym.circle(-640, 0, 45)
    elif kind == "shower":
        sym.rect(0, 0, 900, 900)
        sym.line(-450, -450, 450, 450)
        sym.line(-450, 450, 450, -450)
    elif kind == "kitchen-sink":
        sym.rect(0, 0, 800, 500)
        sym.rect(-190, 0, 300, 380)
        sym.rect(190, 0, 300, 380)
    elif kind == "range":
        sym.rect(0, 0, 700, 600)
        for bx in (-170, 170):
            for by in (-145, 145):
                sym.circle(bx, by, 85)
    elif kind == "refrigerator":
        sym.rect(0, 0, 700, 700)
        sym.label("REF", label_height)
    elif kind == "washer-dryer":
        sym.rect(-300, 0, 600, 600)
        sym.rect(300, 0, 600, 600)
        sym.label("W", label_height, -300, 0)
        sym.label("D", label_height, 300, 0)
    elif kind == "water-heater":
        sym.circle(0, 0, 200)
        sym.label("WH", label_height)
    else:
        assert size is not None
        sym.rect(0, 0, size[0], size[1])
