"""Scaffold: architectural floor plan gen_dxf() template (mm units).

SCOPE — this template declares STRUCTURE: walls, openings, columns, stairs,
rooms, dimensions. Fixtures/detectors/leaders/section bubbles are OPTIONAL
extras (commented examples below); do not add them unless the task asks.

USAGE — do not write from scratch, start from this file:
1. Copy to your workspace next to the intended .dxf output.
2. Edit ONLY the DECLARATION ZONE below. Positions are computed here, at
   declaration time.
3. Run: python scripts/dxf your_file.py   (from the aidxfv1 skill dir)
   The run auto-prints a VALIDATION REPORT — every FAIL must be fixed by
   editing the declaration, never by hacking the assembly zone.
4. Canonicalize, walk the self-check list in references/floor_plan_assembly.md
   sections 3-4 on the declaration + readback. For a visual check use the
   aiblueprint MCP (drawing open -> view screenshot) — it is an aid for
   yourself only; users load the bare .dxf in the frontend.

The ASSEMBLY + VALIDATION ZONES are fixed machinery: do not restructure
them, do not hand-write orientation math anywhere.
"""

import math

import ezdxf

from archdxf import annotate, fixtures, frames, layers, openings, stairs

# ===================== DECLARATION ZONE (edit this) =====================

UNITS = "mm"
W, D = 12000.0, 9000.0           # footprint width x depth
EXT_T, INT_T = 200.0, 100.0      # exterior / partition wall thickness
TXT, ROOM_TXT, TITLE_TXT = 300.0, 450.0, 600.0

# Exterior openings per wall: (kind, offset, width, swing_or_None)
# kind = "door" | "window"; offset measured per vocabulary.md (front/rear
# from the left end, left/right from the front end). door needs a swing
# word (in-left/in-right/out-left/out-right); window must not have one.
EXT_OPENINGS = {
    "front": [
        ("door", 5800.0, 900.0, "in-left"),
        ("window", 3200.0, 1500.0, None),
        ("window", 8600.0, 1500.0, None),
    ],
    "rear": [
        ("window", 1500.0, 1500.0, None),
        ("window", 4800.0, 1200.0, None),
        ("window", 9000.0, 1800.0, None),
    ],
    "left": [("window", 2600.0, 1200.0, None)],
    "right": [
        ("door", 6400.0, 900.0, "out-right"),
        ("window", 2400.0, 1500.0, None),
    ],
}

# Partitions: (axis "x"|"y", offset, span_from, span_to, doors)
# doors: (at, width, swing); `at` is the near jamb along the wall axis.
PARTITIONS = [
    ("x", 5200.0, 0.0, 12000.0, [(3000.0, 800.0, "in-right"), (9500.0, 800.0, "in-left")]),
    ("y", 4000.0, 5200.0, 9000.0, [(6000.0, 700.0, "out-left")]),
]

# Columns: (center, size) — square structural column, drawn poche on A-COLS.
# Example: COLUMNS = [((6000.0, 2600.0), 400.0)]
COLUMNS = []

# Stairs: flights (at, length, width, going, rotation) with going "up"|"dn";
# landings (at, width, depth, rotation). Multi-run stairs are composed by
# the caller: mirrored flights + a landing between them.
STAIR_FLIGHTS = [
    ((1400.0, 2400.0), 3080.0, 1200.0, "up", 0.0),
    ((2700.0, 2400.0), 3080.0, 1200.0, "dn", 0.0),
]
STAIR_LANDINGS = [
    ((2050.0, 4540.0), 2600.0, 1200.0, 0.0),
]

# Rooms: (name, label_point, area_or_None) — area is STATED, never computed.
ROOMS = [
    ("living", (6400.0, 2600.0), 31.0),
    ("kitchen", (9600.0, 2500.0), 10.0),
    ("stair", (2050.0, 480.0), 7.5),
    ("bedroom 1", (2000.0, 7100.0), 12.0),
    ("bath", (6100.0, 7100.0), 6.5),
    ("bedroom 2", (9800.0, 7100.0), 12.5),
]

# ---- OPTIONAL EXTRAS (uncomment only when the task asks) ----------------
# Fixtures: (kind, at, rotation, size_or_None) — kind from fixtures.FIXTURE_TYPES;
# size=(w, d) required for "counter" only; rotation 0 backs onto the +y wall.
# FIXTURES = [
#     ("toilet", (4600.0, 8450.0), 0.0, None),
#     ("kitchen-sink", (8800.0, 500.0), 180.0, None),
#     ("counter", (6500.0, 500.0), 180.0, (2400.0, 600.0)),
# ]
FIXTURES = []

# Detectors: (kind "smoke"|"co"|"combo", at)
# DETECTORS = [("smoke", (2000.0, 7200.0)), ("co", (11000.0, 2600.0))]
DETECTORS = []

# Leaders: (text, tail, target); Section bubbles: (name, sheet, center, dir_vector).
# LEADERS = [("WATER HEATER", (5400.0, 1400.0), (4700.0, 600.0))]
# SECTION_BUBBLES = [("A", "A-501", (9000.0, -2550.0), (0.0, 1.0))]
LEADERS = []
SECTION_BUBBLES = []

TITLE = "FLOOR PLAN"
SCALE_LABEL = "1:100"
NORTH_DEGREES = 0.0              # None = no north arrow

# ===================== ASSEMBLY ZONE (fixed, do not edit) =====================

# Fixture footprints (w, d) in mm, mirroring archdxf.fixtures standard sizes;
# used only for clearance bounding boxes.
_FIXTURE_FOOTPRINTS = {
    "toilet": (400.0, 700.0), "lavatory": (550.0, 450.0),
    "bathtub": (1700.0, 750.0), "shower": (900.0, 900.0),
    "kitchen-sink": (800.0, 500.0), "range": (700.0, 600.0),
    "refrigerator": (700.0, 700.0), "washer-dryer": (1200.0, 600.0),
    "water-heater": (400.0, 400.0),
}


def _frame_local(frame, point):
    dx = point[0] - frame.origin[0]
    dy = point[1] - frame.origin[1]
    return (
        dx * frame.s_dir[0] + dy * frame.s_dir[1],
        dx * frame.d_dir[0] + dy * frame.d_dir[1],
    )


def gen_dxf():
    ezdxf.options.write_fixed_meta_data_for_testing = True
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM if UNITS == "mm" else ezdxf.units.FT
    layers.ensure_layers(doc, "floor")
    annotate.ensure_dimstyle(doc, text_height=TXT)
    msp = doc.modelspace()

    ext = frames.rect_wall_frames(W, D)
    door_groups: dict[float, list] = {}
    window_groups: dict[float, list] = {}
    door_specs = []   # (frame, s_start, width, swing, thickness, wall_id)
    wall_solids = []  # (frame, solid_spans, thickness, wall_id)

    for name in ("front", "rear", "left", "right"):
        frame = ext[name]
        cuts = [(o[1], o[1] + o[2]) for o in EXT_OPENINGS[name]]
        hatch_span = (0.0, frame.length) if name in ("front", "rear") else (
            EXT_T, frame.length - EXT_T,
        )
        openings.wall_run(
            msp, frame, (0.0, frame.length), EXT_T, cuts, "A-WALL", hatch_span=hatch_span
        )
        wall_solids.append((frame, (0.0, frame.length), cuts, EXT_T, f"exterior {name}"))
        for kind, s, width, swing in EXT_OPENINGS[name]:
            openings.jamb_pair(msp, frame, s, width, EXT_T, "A-WALL")
            if kind == "door":
                openings.door_leaf(msp, frame, s, width, swing, EXT_T)
                door_groups.setdefault(width, []).append((frame, s))
                door_specs.append((frame, s, width, swing, EXT_T, f"exterior {name} door@{s:g}"))
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
        wall_solids.append((frame, (lo, hi), cuts, INT_T, f"partition {axis}@{offset:g}"))
        for at, width, swing in doors:
            openings.jamb_pair(msp, frame, at, width, INT_T, "A-WALL-INTR")
            openings.door_leaf(msp, frame, at, width, swing, INT_T)
            door_groups.setdefault(width, []).append((frame, at))
            door_specs.append((frame, at, width, swing, INT_T, f"partition {axis}@{offset:g} door@{at:g}"))
        if span_from > EXT_T:
            openings.partition_end_cap(msp, frame, lo, INT_T, "A-WALL-INTR")
        if span_to < along - EXT_T:
            openings.partition_end_cap(msp, frame, hi, INT_T, "A-WALL-INTR")

    for center, size in COLUMNS:
        cx, cy = center
        half = size / 2
        msp.add_lwpolyline(
            [(cx - half, cy - half), (cx + half, cy - half),
             (cx + half, cy + half), (cx - half, cy + half)],
            close=True, dxfattribs={"layer": "A-COLS"},
        )
        hatch = msp.add_hatch(color=7, dxfattribs={"layer": "A-COLS"})
        hatch.set_solid_fill()
        hatch.paths.add_polyline_path(
            [(cx - half, cy - half), (cx + half, cy - half),
             (cx + half, cy + half), (cx - half, cy + half)], is_closed=True,
        )

    for groups, prefix in ((door_groups, "D"), (window_groups, "W")):
        for index, width in enumerate(sorted(groups), start=1):
            for frame, s in groups[width]:
                annotate.add_tag(
                    msp, f"{prefix}{index}", frame.point(s + width / 2, -2.3 * TXT),
                    radius=TXT, text_height=TXT,
                )

    for name, at, area in ROOMS:
        annotate.room_label(
            msp, name, at, height=ROOM_TXT, area=area,
            area_text=f"{area:g} M2" if (UNITS == "mm" and area is not None) else None,
        )

    for kind, at, rotation, size in FIXTURES:
        fixtures.draw_fixture(msp, kind, at, rotation=rotation, size=size, label_height=TXT * 0.6)

    for at, length, width, going, rotation in STAIR_FLIGHTS:
        stairs.draw_stair_flight(
            msp, at, length=length, width=width, going=going,
            rotation=rotation, label_height=TXT * 0.6,
        )
    for at, width, depth, rotation in STAIR_LANDINGS:
        stairs.draw_landing(msp, at, width=width, depth=depth, rotation=rotation)

    for kind, at in DETECTORS:
        annotate.detector_symbol(msp, kind, at, radius=TXT * 0.8, text_height=TXT)

    for text, tail, target in LEADERS:
        annotate.add_leader(msp, text, tail, target, height=TXT)

    for name, sheet, center, direction in SECTION_BUBBLES:
        annotate.section_bubble(
            msp, name, sheet, center, direction, radius=1.5 * TXT, text_height=TXT,
        )

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
    annotate.view_title(
        msp, TITLE, (W / 2, -10.7 * TXT), height=TITLE_TXT, scale_label=SCALE_LABEL,
    )

    _validate(door_specs, wall_solids)
    return doc


# ===================== VALIDATION ZONE (fixed, do not edit) =====================
# Auto-checks run on every gen_dxf() and print a report. Implements the
# geometrically decidable rules of building_types/_template.md section T0:
# U-A1 junction continuity, U-A2 pier clearance, U-A3/U-D3 swing clearance,
# U-D1 column-vs-opening. Fix every FAIL in the DECLARATION ZONE; a WARN
# needs a human look.

_TOL = 1.0


def _swing_points(frame, s_start, width, swing, thickness, steps=12):
    """Sample the door leaf tip along its 90-degree swing, in plan coords."""
    inward = swing.startswith("in")
    hinge_left = swing.endswith("left")
    face_d = thickness if inward else 0.0
    hinge_s = s_start if hinge_left else s_start + width
    s_sign = 1.0 if hinge_left else -1.0
    d_sign = 1.0 if inward else -1.0
    for i in range(steps + 1):
        phi = (i / steps) * math.pi / 2
        yield frame.point(
            hinge_s + s_sign * width * math.cos(phi),
            face_d + d_sign * width * math.sin(phi),
        )


def _point_in_wall(frame, span, thickness, point):
    s, d = _frame_local(frame, point)
    return span[0] + _TOL < s < span[1] - _TOL and _TOL < d < thickness - _TOL


def _point_in_gap(frame, cut, thickness, point):
    s, d = _frame_local(frame, point)
    return cut[0] - _TOL <= s <= cut[1] + _TOL and -_TOL <= d <= thickness + _TOL


def _point_in_box(center, size_w, size_d, rotation, point):
    half_w, half_d = (size_w, size_d) if rotation % 180 == 0 else (size_d, size_w)
    return (
        abs(point[0] - center[0]) < half_w / 2 - _TOL
        and abs(point[1] - center[1]) < half_d / 2 - _TOL
    )


def _validate(door_specs, wall_solids):
    issues = []

    for name in ("front", "rear", "left", "right"):
        length = W if name in ("front", "rear") else D
        cuts = sorted((o[1], o[1] + o[2], o[0]) for o in EXT_OPENINGS[name])
        for start, end, kind in cuts:
            if start < 0 or end > length:
                issues.append(("FAIL", f"{name} {kind}@{start:g}: opening [{start:g},{end:g}] exceeds wall length {length:g}"))
        for (s1, e1, k1), (s2, e2, k2) in zip(cuts, cuts[1:]):
            if s2 < e1:
                issues.append(("FAIL", f"{name}: {k1}@{s1:g} overlaps {k2}@{s2:g}"))

    for axis, offset, span_from, span_to, doors in PARTITIONS:
        along = W if axis == "x" else D
        if not (0 <= span_from < span_to <= along):
            issues.append(("FAIL", f"partition {axis}@{offset:g}: span [{span_from:g},{span_to:g}] outside [0,{along:g}]"))
        cuts = sorted((a, a + w) for a, w, _sw in doors)
        for start, end in cuts:
            if start < span_from or end > span_to:
                issues.append(("FAIL", f"partition {axis}@{offset:g}: door [{start:g},{end:g}] outside declared span"))
        for (s1, e1), (s2, _e2) in zip(cuts, cuts[1:]):
            if s2 < e1:
                issues.append(("FAIL", f"partition {axis}@{offset:g}: overlapping doors at {s1:g}/{s2:g}"))

    # U-A1 junction continuity: an opening gap must not contain another wall's
    # body (crossing), and a partition end must not land on an opening.
    for frame, _span, cuts, thickness, wall_id in wall_solids:
        for s1, s2 in cuts:
            samples = [frame.point(s1 + (s2 - s1) * k / 4, thickness / 2) for k in range(5)]
            samples += [frame.point((s1 + s2) / 2, 0.0), frame.point((s1 + s2) / 2, thickness)]
            for o_frame, o_span, _o_cuts, o_thick, o_id in wall_solids:
                if o_id == wall_id:
                    continue
                if any(_point_in_wall(o_frame, o_span, o_thick, p) for p in samples):
                    issues.append(("FAIL", f"{wall_id}: opening [{s1:g},{s2:g}] crosses {o_id}"))
                    break
    for b_frame, b_span, _b_cuts, b_thick, b_id in wall_solids:
        if not b_id.startswith("partition"):
            continue
        for end_s in b_span:
            end_pt = b_frame.point(end_s, b_thick / 2)
            for a_frame, _a_span, a_cuts, a_thick, a_id in wall_solids:
                if a_id == b_id:
                    continue
                for cut in a_cuts:
                    if _point_in_gap(a_frame, cut, a_thick, end_pt):
                        issues.append(("FAIL", f"{b_id}: wall end lands on {a_id} opening [{cut[0]:g},{cut[1]:g}]"))

    # U-A2 pier/jamb clearance: remaining wall between an opening edge and a
    # corner or the next opening must be at least one wall thickness.
    for name in ("front", "rear", "left", "right"):
        length = W if name in ("front", "rear") else D
        cuts = sorted((o[1], o[1] + o[2]) for o in EXT_OPENINGS[name])
        for s1, s2 in cuts:
            if s1 < EXT_T or s2 > length - EXT_T:
                issues.append(("WARN", f"{name}: opening [{s1:g},{s2:g}] jamb clearance < wall thickness {EXT_T:g}"))
        for (_a1, a2), (b1, _b2) in zip(cuts, cuts[1:]):
            if b1 - a2 < EXT_T:
                issues.append(("WARN", f"{name}: pier between openings [{_a1:g},{a2:g}]/[{b1:g},{_b2:g}] < wall thickness"))
    for axis, offset, span_from, span_to, doors in PARTITIONS:
        for at, width, _sw in doors:
            if at - span_from < EXT_T or span_to - (at + width) < EXT_T:
                issues.append(("WARN", f"partition {axis}@{offset:g}: door [{at:g},{at + width:g}] jamb clearance < {EXT_T:g}"))

    # U-D1: columns must not intrude into door/window openings.
    for center, size in COLUMNS:
        cx, cy = center
        half = size / 2
        samples = [(cx + dx, cy + dy) for dx in (-half, 0.0, half) for dy in (-half, 0.0, half)]
        for a_frame, _span, a_cuts, a_thick, a_id in wall_solids:
            for cut in a_cuts:
                hit = any(_point_in_gap(a_frame, cut, a_thick, p) for p in samples)
                if not hit:
                    gm = a_frame.point((cut[0] + cut[1]) / 2, a_thick / 2)
                    hit = abs(gm[0] - cx) < half and abs(gm[1] - cy) < half
                if hit:
                    issues.append(("FAIL", f"column@{tuple(int(v) for v in center)}: overlaps {a_id} opening [{cut[0]:g},{cut[1]:g}]"))

    for frame, s_start, width, swing, thickness, door_id in door_specs:
        blocked = None
        for point in _swing_points(frame, s_start, width, swing, thickness):
            for w_frame, span, cuts, w_thick, wall_id in wall_solids:
                if wall_id.split(" door")[0] == door_id.rsplit(" door", 1)[0]:
                    own_cuts = cuts
                else:
                    own_cuts = []
                s_loc, _d = _frame_local(w_frame, point)
                in_cut = any(c[0] - _TOL <= s_loc <= c[1] + _TOL for c in own_cuts)
                if in_cut:
                    continue
                if _point_in_wall(w_frame, span, w_thick, point):
                    blocked = f"swing blocked by {wall_id} near ({point[0]:.0f},{point[1]:.0f})"
                    break
            if blocked:
                break
            for center, size in COLUMNS:
                if _point_in_box(center, size, size, 0.0, point):
                    blocked = f"swing blocked by column@{tuple(int(v) for v in center)}"
                    break
            if blocked:
                break
            for kind, at, rotation, size in FIXTURES:
                fw, fd = size if kind == "counter" else _FIXTURE_FOOTPRINTS[kind]
                if _point_in_box(at, fw, fd, rotation, point):
                    blocked = f"swing blocked by {kind}@{tuple(int(v) for v in at)}"
                    break
            if blocked:
                break
        if blocked:
            issues.append(("FAIL", f"{door_id}: {blocked}"))

    for center, size in COLUMNS:
        cx, cy = center
        half = size / 2
        if not (0 <= cx - half and cx + half <= W and 0 <= cy - half and cy + half <= D):
            issues.append(("WARN", f"column@{tuple(int(v) for v in center)}: outside footprint"))
    for name, at, _area in ROOMS:
        if not (0 <= at[0] <= W and 0 <= at[1] <= D):
            issues.append(("WARN", f"room {name!r}: label point outside footprint"))
    for at, length, width, _going, rotation in STAIR_FLIGHTS:
        lx, ly = (width, length) if rotation % 180 == 0 else (length, width)
        if not (0 <= at[0] - lx / 2 and at[0] + lx / 2 <= W and 0 <= at[1] - ly / 2 and at[1] + ly / 2 <= D):
            issues.append(("WARN", f"stair flight@{tuple(int(v) for v in at)}: extends outside footprint"))

    fails = sum(1 for level, _m in issues if level == "FAIL")
    warns = sum(1 for level, _m in issues if level == "WARN")
    print(f"[validate] --- {fails} FAIL, {warns} WARN ---")
    for level, message in issues:
        print(f"[validate] {level}: {message}")
    if not issues:
        print("[validate] all checks passed")
