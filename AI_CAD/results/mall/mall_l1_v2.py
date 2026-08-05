"""Mall L1 regression case, rebuilt on archdxf (mm units).

Same scheme as mall_l1 (150m x 100m, double-loaded street + atrium,
40 retail units + 2 anchors) but all construction goes through archdxf:
storefronts declared as (wall, offset, width) opening triples expanded
by the library, no hand-written orientation math.
"""

import ezdxf

from archdxf import annotate, frames, layers, openings
from archdxf.frames import WallFrame

W, D = 150000.0, 100000.0
STREET_X0, STREET_X1 = 25000.0, 125000.0
STREET_Y0, STREET_Y1 = 44000.0, 56000.0
SHOP_DEPTH = 16000.0
BOH = 6000.0
SHOP_W = 10000.0
EXT_T, INT_T = 400.0, 200.0
STOREFRONT_W = 8000.0
ENTRANCE_W = 12000.0
TXT = 2000.0

MALL_LAYERS = dict(layers.FLOOR_LAYERS)
MALL_LAYERS["A-VOID"] = {"color": 8, "lineweight": 18}


def gen_dxf():
    ezdxf.options.write_fixed_meta_data_for_testing = True
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    layers.ensure_layers(doc, MALL_LAYERS)
    annotate.ensure_dimstyle(doc, text_height=1800.0)
    annotate.ensure_dimstyle(doc, "ARCHDXF-SM", text_height=700.0)
    msp = doc.modelspace()

    def label(text, at, height=TXT, layer="A-ANNO-TEXT"):
        msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(
            at, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER
        )

    ext = frames.rect_wall_frames(W, D)
    entrance_south = (W - ENTRANCE_W) / 2
    entrance_side = (D - ENTRANCE_W) / 2
    ext_cuts = {
        "front": [(entrance_south, entrance_south + ENTRANCE_W)],
        "rear": [(entrance_south, entrance_south + ENTRANCE_W)],
        "left": [(entrance_side, entrance_side + ENTRANCE_W)],
        "right": [(entrance_side, entrance_side + ENTRANCE_W)],
    }
    for name in ("front", "rear", "left", "right"):
        frame = ext[name]
        cuts = ext_cuts[name]
        hatch_span = (0.0, frame.length) if name in ("front", "rear") else (
            EXT_T, frame.length - EXT_T,
        )
        openings.wall_run(msp, frame, (0.0, frame.length), EXT_T, cuts, "A-WALL", hatch_span=hatch_span)
        for s0, s1 in cuts:
            openings.jamb_pair(msp, frame, s0, s1 - s0, EXT_T, "A-WALL")

    label("ENTRANCE", (W / 2, -6000), height=3000)
    label("ENTRANCE", (W / 2, D + 6000), height=3000)
    label("ENTRANCE", (-6000, D / 2), height=3000)
    label("ENTRANCE", (W + 6000, D / 2), height=3000)

    street_len = STREET_X1 - STREET_X0
    storefront_cuts = []
    k = 0
    while k * SHOP_W < street_len:
        s = k * SHOP_W + (SHOP_W - STOREFRONT_W) / 2
        storefront_cuts.append((s, s + STOREFRONT_W))
        k += 1
    n_bays = k

    for y_face, d_dir in ((STREET_Y0, -1.0), (STREET_Y1, 1.0)):
        frame = WallFrame((STREET_X0, y_face), (1.0, 0.0), (0.0, d_dir), street_len)
        openings.wall_run(
            msp, frame, (0.0, street_len), INT_T, storefront_cuts, "A-WALL-INTR",
            inner_span=(0.0, street_len), hatch_span=(0.0, street_len),
        )
        for s0, s1 in storefront_cuts:
            openings.jamb_pair(msp, frame, s0, s1 - s0, INT_T, "A-WALL-INTR")
            openings.window_line(msp, frame, s0, s1 - s0, INT_T)

    label("ATRIUM", ((STREET_X0 + STREET_X1) / 2, (STREET_Y0 + STREET_Y1) / 2), height=5000)

    shop_south0 = STREET_Y0 - SHOP_DEPTH
    shop_north1 = STREET_Y1 + SHOP_DEPTH
    band_walls = (
        (shop_south0, "RETAIL 10m UNITS", (shop_south0 + STREET_Y0) / 2),
        (shop_north1, "RETAIL 10m UNITS", (STREET_Y1 + shop_north1) / 2),
        (shop_south0 - BOH, "BOH CORRIDOR", (shop_south0 - BOH + shop_south0) / 2),
        (shop_north1 + BOH, "BOH CORRIDOR", (shop_north1 + shop_north1 + BOH) / 2),
    )
    for y, name, label_y in band_walls:
        frame = frames.partition_frame("x", y, INT_T, W)
        openings.wall_run(
            msp, frame, (STREET_X0, STREET_X1), INT_T, [], "A-WALL-INTR",
            inner_span=(STREET_X0, STREET_X1), hatch_span=(STREET_X0, STREET_X1),
        )
        label(name, ((STREET_X0 + STREET_X1) / 2, label_y), height=2500)

    retail_bands = (
        (EXT_T, shop_south0 - BOH, "SOUTH RETAIL"),
        (shop_north1 + BOH, D - EXT_T, "NORTH RETAIL"),
    )
    for band_y0, band_y1, name in retail_bands:
        x = STREET_X0
        while x <= STREET_X1:
            frame = frames.partition_frame("y", x, INT_T, D)
            openings.wall_run(
                msp, frame, (band_y0, band_y1), INT_T, [], "A-WALL-INTR",
                inner_span=(band_y0, band_y1), hatch_span=(band_y0, band_y1),
            )
            x += SHOP_W
        label(name, ((STREET_X0 + STREET_X1) / 2, (band_y0 + band_y1) / 2), height=2500)

    for y0, y1 in ((shop_south0, STREET_Y0), (STREET_Y1, shop_north1)):
        x = STREET_X0
        while x <= STREET_X1:
            frame = frames.partition_frame("y", x, INT_T, D)
            openings.wall_run(
                msp, frame, (y0, y1), INT_T, [], "A-WALL-INTR",
                inner_span=(y0, y1), hatch_span=(y0, y1),
            )
            x += SHOP_W

    for x_anchor in (STREET_X0, STREET_X1):
        frame = frames.partition_frame("y", x_anchor, INT_T, D)
        openings.wall_run(
            msp, frame, (EXT_T, D - EXT_T), INT_T, [], "A-WALL-INTR",
            inner_span=(EXT_T, D - EXT_T), hatch_span=(EXT_T, D - EXT_T),
        )
    label("ANCHOR STORE", (STREET_X0 / 2, 15000), height=3500)
    label("ANCHOR STORE", ((W + STREET_X1) / 2, 15000), height=3500)

    for kx in range(n_bays + 1):
        x = STREET_X0 + kx * SHOP_W
        for y in (STREET_Y0, STREET_Y1):
            msp.add_lwpolyline(
                [(x - 300, y - 300), (x + 300, y - 300), (x + 300, y + 300), (x - 300, y + 300)],
                close=True, dxfattribs={"layer": "A-COLS"},
            )

    for cx, cy, w, h, name in (
        (55000, 50000, 10000, 4000, "ESC"),
        (95000, 50000, 10000, 4000, "ESC"),
        (40000, 25000, 8000, 5600, "CORE"),
        (110000, 75000, 8000, 5600, "CORE"),
    ):
        x0, y0 = cx - w / 2, cy - h / 2
        msp.add_lwpolyline(
            [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
            close=True, dxfattribs={"layer": "A-WALL-INTR"},
        )
        label(name, (cx, cy))

    bay_stations = [k * SHOP_W for k in range(n_bays + 1)]
    annotate.dim_chain(
        msp, bay_stations, lambda s: (STREET_X0 + s, STREET_Y0 + 1500.0),
        angle=0.0, base=(STREET_X0, STREET_Y0 + 1500.0),
        dimstyle="ARCHDXF-SM", unit="mm",
    )
    annotate.add_dim(msp, (0.0, 0.0), (W, 0.0), angle=0.0, base=(0.0, -14000.0), unit="mm")
    annotate.add_dim(msp, (0.0, 0.0), (0.0, D), angle=90.0, base=(-18000.0, 0.0), unit="mm")

    annotate.view_title(msp, "SHOPPING MALL L1  150m x 100m", (W / 2, D + 14000.0), height=5000.0)
    return doc
