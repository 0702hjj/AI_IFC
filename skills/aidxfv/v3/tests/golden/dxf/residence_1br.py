"""Golden case: 1BR residence floor plan via archdxf (mm units).

Exercises the full assembly invariant: exterior walls with door+windows,
partitions with doors, room labels, fixtures, detectors, dimension
chains, overall dims, tags, north arrow, view title.
"""

import ezdxf

from archdxf import annotate, fixtures, frames, openings, layers

W, D = 8000.0, 6000.0
EXT_T, INT_T = 200.0, 100.0
TXT, ROOM_TXT, TITLE_TXT = 300.0, 450.0, 600.0

EXT_OPENINGS = {
    "front": [("door", 3200.0, 900.0, "in-left"), ("window", 600.0, 1500.0, None)],
    "rear": [("window", 1200.0, 1500.0, None), ("window", 5400.0, 1200.0, None)],
    "left": [("window", 600.0, 1500.0, None)],
    "right": [],
}
PARTITIONS = [
    ("x", 3600.0, 0.0, 8000.0, [(2200.0, 800.0, "in-left")]),
    ("y", 5600.0, 3600.0, 6000.0, [(4200.0, 700.0, "in-right")]),
]


def gen_dxf():
    ezdxf.options.write_fixed_meta_data_for_testing = True
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    layers.ensure_layers(doc, "floor")
    annotate.ensure_dimstyle(doc, text_height=TXT)
    msp = doc.modelspace()

    ext = frames.rect_wall_frames(W, D)

    for name in ("front", "rear", "left", "right"):
        frame = ext[name]
        cuts = [(o[1], o[1] + o[2]) for o in EXT_OPENINGS[name]]
        hatch_span = (0.0, frame.length) if name in ("front", "rear") else (
            EXT_T,
            frame.length - EXT_T,
        )
        openings.wall_run(
            msp, frame, (0.0, frame.length), EXT_T, cuts, "WALL", hatch_span=hatch_span
        )
        for kind, s, width, swing in EXT_OPENINGS[name]:
            openings.jamb_pair(msp, frame, s, width, EXT_T, "WALL")
            if kind == "door":
                openings.door_leaf(msp, frame, s, width, swing, EXT_T)
                annotate.add_tag(
                    msp, "D1", frame.point(s + width / 2, -700), radius=300, text_height=TXT
                )
            else:
                openings.window_line(msp, frame, s, width, EXT_T)

    for axis, offset, span_from, span_to, doors in PARTITIONS:
        along = W if axis == "x" else D
        frame = frames.partition_frame(axis, offset, INT_T, along)
        lo = max(span_from, EXT_T)
        hi = min(span_to, along - EXT_T)
        cuts = [(d[0], d[0] + d[1]) for d in doors]
        openings.wall_run(
            msp, frame, (lo, hi), INT_T, cuts, "WALL",
            inner_span=(lo, hi), hatch_span=(lo, hi),
        )
        for at, width, swing in doors:
            openings.jamb_pair(msp, frame, at, width, INT_T, "WALL")
            openings.door_leaf(msp, frame, at, width, swing, INT_T)
        if span_from > EXT_T:
            openings.partition_end_cap(msp, frame, lo, INT_T, "WALL")
        if span_to < along - EXT_T:
            openings.partition_end_cap(msp, frame, hi, INT_T, "WALL")

    annotate.room_label(msp, "living", (4000, 1700), height=ROOM_TXT, area=26.6, area_text="26.6 M2")
    annotate.room_label(msp, "bedroom", (2800, 4800), height=ROOM_TXT, area=13.4, area_text="13.4 M2")
    annotate.room_label(msp, "bath", (6800, 4500), height=ROOM_TXT, area=5.6, area_text="5.6 M2")

    fixtures.draw_fixture(msp, "toilet", (6700, 5300))
    fixtures.draw_fixture(msp, "lavatory", (7450, 3950), rotation=90)
    fixtures.draw_fixture(msp, "shower", (6100, 5400))
    fixtures.draw_fixture(msp, "kitchen-sink", (900, 3250))
    fixtures.draw_fixture(msp, "range", (1900, 3250))
    fixtures.draw_fixture(msp, "counter", (1400, 3250), size=(2000, 600))

    annotate.detector_symbol(msp, "smoke", (1500, 4200), radius=250, text_height=TXT)
    annotate.detector_symbol(msp, "combo", (4000, 3200), radius=250, text_height=TXT)

    chain_rows = {
        "front": (lambda s: (s, 0.0), 0.0, (0.0, -1300.0)),
        "rear": (lambda s: (s, D), 0.0, (0.0, D + 1100.0)),
        "left": (lambda s: (0.0, s), 90.0, (-1100.0, 0.0)),
        "right": (lambda s: (W, s), 90.0, (W + 1100.0, 0.0)),
    }
    for name, (to_point, angle, base) in chain_rows.items():
        ops = sorted(EXT_OPENINGS[name], key=lambda o: o[1])
        if not ops:
            continue
        stations = [0.0]
        for _kind, s, width, _swing in ops:
            stations += [s, s + width]
        stations.append(ext[name].length)
        annotate.dim_chain(msp, stations, to_point, angle=angle, base=base, unit="mm")

    annotate.add_dim(msp, (0.0, 0.0), (W, 0.0), angle=0.0, base=(0.0, -2100.0), unit="mm")
    annotate.add_dim(msp, (0.0, 0.0), (0.0, D), angle=90.0, base=(-1900.0, 0.0), unit="mm")
    annotate.add_dim(msp, (0.0, D), (W, D), angle=0.0, base=(0.0, D + 1900.0), unit="mm")

    annotate.north_arrow(msp, (W + 1600.0, D + 1300.0), size=900.0)
    annotate.view_title(msp, "FLOOR PLAN 1BR", (W / 2, -3200.0), height=TITLE_TXT)
    return doc
