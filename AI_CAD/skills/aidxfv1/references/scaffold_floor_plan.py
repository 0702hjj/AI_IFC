"""Scaffold: architectural floor plan gen_dxf() template (mm units).

USAGE — do not write from scratch, start from this file:
1. Copy to your workspace next to the intended .dxf output.
2. Edit ONLY the DECLARATION ZONE below (sizes, walls, openings, rooms,
   fixtures). Positions are computed here, at declaration time.
3. Run: python scripts/dxf your_file.py   (from the aidxfv1 skill dir)
4. Canonicalize + render preview, then self-review against
   references/floor_plan_assembly.md sections 3-4.

The ASSEMBLY ZONE is fixed machinery: do not restructure it, do not
hand-write orientation math anywhere.
"""

import ezdxf

from archdxf import annotate, fixtures, frames, layers, openings

# ===================== DECLARATION ZONE (edit this) =====================

UNITS = "mm"
W, D = 8000.0, 6000.0            # footprint width x depth
EXT_T, INT_T = 200.0, 100.0      # exterior / partition wall thickness
TXT, ROOM_TXT, TITLE_TXT = 300.0, 450.0, 600.0

# Exterior openings per wall: (kind, offset, width, swing_or_None)
# kind = "door" | "window"; offset measured per vocabulary.md (front/rear
# from the left end, left/right from the front end). door needs a swing
# word (in-left/in-right/out-left/out-right); window must not have one.
EXT_OPENINGS = {
    "front": [("door", 3200.0, 900.0, "in-left"), ("window", 600.0, 1500.0, None)],
    "rear": [("window", 1200.0, 1500.0, None)],
    "left": [],
    "right": [],
}

# Partitions: (axis "x"|"y", offset, span_from, span_to, doors)
# doors: (at, width, swing); `at` is the near jamb along the wall axis.
PARTITIONS = [
    ("x", 3600.0, 0.0, 8000.0, [(2200.0, 800.0, "in-left")]),
]

# Rooms: (name, label_point, area_or_None) — area is STATED, never computed.
ROOMS = [
    ("living", (4000.0, 1700.0), 26.6),
    ("bedroom", (2800.0, 4800.0), 13.4),
]

# Fixtures: (kind, at, rotation, size_or_None) — kind from fixtures.FIXTURE_TYPES.
FIXTURES = [
    ("kitchen-sink", (900.0, 3250.0), 0.0, None),
]

# Detectors: (kind "smoke"|"co"|"combo", at)
DETECTORS = [("smoke", (1500.0, 4200.0))]

TITLE = "FLOOR PLAN"
NORTH_DEGREES = None             # None = no north arrow

# ===================== ASSEMBLY ZONE (fixed, do not edit) =====================


def gen_dxf():
    ezdxf.options.write_fixed_meta_data_for_testing = True
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM if UNITS == "mm" else ezdxf.units.FT
    layers.ensure_layers(doc, "floor")
    annotate.ensure_dimstyle(doc, text_height=TXT)
    msp = doc.modelspace()

    ext = frames.rect_wall_frames(W, D)

    for name in ("front", "rear", "left", "right"):
        frame = ext[name]
        cuts = [(o[1], o[1] + o[2]) for o in EXT_OPENINGS[name]]
        hatch_span = (0.0, frame.length) if name in ("front", "rear") else (
            EXT_T, frame.length - EXT_T,
        )
        openings.wall_run(
            msp, frame, (0.0, frame.length), EXT_T, cuts, "A-WALL", hatch_span=hatch_span
        )
        for kind, s, width, swing in EXT_OPENINGS[name]:
            openings.jamb_pair(msp, frame, s, width, EXT_T, "A-WALL")
            if kind == "door":
                openings.door_leaf(msp, frame, s, width, swing, EXT_T)
            else:
                openings.window_line(msp, frame, s, width, EXT_T)

    for axis, offset, span_from, span_to, doors in PARTITIONS:
        along = W if axis == "x" else D
        frame = frames.partition_frame(axis, offset, INT_T, along)
        lo = max(span_from, EXT_T)
        hi = min(span_to, along - EXT_T)
        cuts = [(d[0], d[0] + d[1]) for d in doors]
        openings.wall_run(
            msp, frame, (lo, hi), INT_T, cuts, "A-WALL-INTR",
            inner_span=(lo, hi), hatch_span=(lo, hi),
        )
        for at, width, swing in doors:
            openings.jamb_pair(msp, frame, at, width, INT_T, "A-WALL-INTR")
            openings.door_leaf(msp, frame, at, width, swing, INT_T)
        if span_from > EXT_T:
            openings.partition_end_cap(msp, frame, lo, INT_T, "A-WALL-INTR")
        if span_to < along - EXT_T:
            openings.partition_end_cap(msp, frame, hi, INT_T, "A-WALL-INTR")

    for name, at, area in ROOMS:
        annotate.room_label(msp, name, at, height=ROOM_TXT, area=area)

    for kind, at, rotation, size in FIXTURES:
        fixtures.draw_fixture(msp, kind, at, rotation=rotation, size=size)

    for kind, at in DETECTORS:
        annotate.detector_symbol(msp, kind, at, radius=TXT * 0.8, text_height=TXT)

    chain_rows = {
        "front": (lambda s: (s, 0.0), 0.0, (0.0, -3.7 * TXT)),
        "rear": (lambda s: (s, D), 0.0, (0.0, D + 3.7 * TXT)),
        "left": (lambda s: (0.0, s), 90.0, (-3.7 * TXT, 0.0)),
        "right": (lambda s: (W, s), 90.0, (W + 3.7 * TXT, 0.0)),
    }
    for name, (to_point, angle, base) in chain_rows.items():
        ops = sorted(EXT_OPENINGS[name], key=lambda o: o[1])
        if not ops:
            continue
        stations = [0.0]
        for _kind, s, width, _swing in ops:
            stations += [s, s + width]
        stations.append(ext[name].length)
        annotate.dim_chain(msp, stations, to_point, angle=angle, base=base, unit=UNITS)

    annotate.add_dim(msp, (0.0, 0.0), (W, 0.0), angle=0.0, base=(0.0, -6.3 * TXT), unit=UNITS)
    annotate.add_dim(msp, (0.0, 0.0), (0.0, D), angle=90.0, base=(-6.3 * TXT, 0.0), unit=UNITS)
    walls_with_openings = {n for n, ops in EXT_OPENINGS.items() if ops}
    if "rear" in walls_with_openings:
        annotate.add_dim(msp, (0.0, D), (W, D), angle=0.0, base=(0.0, D + 6.3 * TXT), unit=UNITS)
    if "right" in walls_with_openings:
        annotate.add_dim(msp, (W, 0.0), (W, D), angle=90.0, base=(W + 6.3 * TXT, 0.0), unit=UNITS)

    if NORTH_DEGREES is not None:
        annotate.north_arrow(
            msp, (W + 5.3 * TXT, D + 4.3 * TXT), size=3.0 * TXT,
            rotation_degrees=NORTH_DEGREES,
        )
    annotate.view_title(msp, TITLE, (W / 2, -10.7 * TXT), height=TITLE_TXT)
    return doc
