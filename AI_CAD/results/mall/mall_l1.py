import ezdxf
from ezdxf.enums import TextEntityAlignment

W, D = 150000.0, 100000.0
STREET_X0, STREET_X1 = 25000.0, 125000.0
STREET_Y0, STREET_Y1 = 44000.0, 56000.0
SHOP_DEPTH = 16000.0
BOH = 6000.0
SHOP_W = 10000.0
WALL_T = 400.0

LAYERS = {
    "A-WALL": {"color": 7, "lineweight": 50},
    "A-WALL-INTR": {"color": 7, "lineweight": 25},
    "A-VOID": {"color": 4, "lineweight": 25, "linetype": "DASHED"},
    "A-COLS": {"color": 7, "lineweight": 35},
    "A-CORE": {"color": 2, "lineweight": 35},
    "A-DOOR": {"color": 4, "lineweight": 25},
    "A-ANNO": {"color": 7, "lineweight": 18},
}


def wall(msp, pts, layer="A-WALL"):
    e = msp.add_lwpolyline(pts, dxfattribs={"layer": layer})
    e.dxf.const_width = WALL_T if layer == "A-WALL" else 200.0
    return e


def line(msp, p1, p2, layer):
    msp.add_line(p1, p2, dxfattribs={"layer": layer})


def label(msp, text, at, height=3000, layer="A-ANNO"):
    msp.add_text(text, dxfattribs={"layer": layer, "height": height}).set_placement(
        at, align=TextEntityAlignment.MIDDLE_CENTER
    )


def rect(msp, x0, y0, x1, y1, layer):
    msp.add_lwpolyline(
        [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": layer}
    )


def core(msp, cx, cy, w, h, name):
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    rect(msp, x0, y0, x1, y1, "A-CORE")
    line(msp, (x0, y0), (x1, y1), "A-CORE")
    line(msp, (x0, y1), (x1, y0), "A-CORE")
    label(msp, name, (cx, cy), height=2000)


def gen_dxf():
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    for name, attribs in LAYERS.items():
        doc.layers.add(name, **attribs)
    msp = doc.modelspace()

    ex, ny = 12000.0, 12000.0
    gxs, gxe = W / 2 - ex / 2, W / 2 + ex / 2
    gys, gye = D / 2 - ny / 2, D / 2 + ny / 2
    wall(msp, [(0, 0), (gxs, 0)])
    wall(msp, [(gxe, 0), (W, 0)])
    wall(msp, [(0, D), (gxs, D)])
    wall(msp, [(gxe, D), (W, D)])
    wall(msp, [(0, 0), (0, gys)])
    wall(msp, [(0, gye), (0, D)])
    wall(msp, [(W, 0), (W, gys)])
    wall(msp, [(W, gye), (W, D)])
    for gx in (gxs, gxe):
        label(msp, "ENTRANCE", (W / 2, -3500 if gx == gxs else D + 3500), height=2500)
    label(msp, "ENTRANCE", (-6000, D / 2), height=2500)
    label(msp, "ENTRANCE", (W + 6000, D / 2), height=2500)

    sy0, sy1 = STREET_Y0, STREET_Y1
    rect(msp, STREET_X0, sy0, STREET_X1, sy1, "A-VOID")
    label(msp, "ATRIUM", ((STREET_X0 + STREET_X1) / 2, (sy0 + sy1) / 2), height=4000)

    s0, s1 = STREET_Y0 - SHOP_DEPTH, STREET_Y0
    n0, n1 = STREET_Y1, STREET_Y1 + SHOP_DEPTH
    wall(msp, [(STREET_X0, s0), (STREET_X1, s0)], layer="A-WALL-INTR")
    wall(msp, [(STREET_X0, n1), (STREET_X1, n1)], layer="A-WALL-INTR")
    k = 0
    while STREET_X0 + k * SHOP_W <= STREET_X1:
        x = STREET_X0 + k * SHOP_W
        line(msp, (x, s0), (x, s1), "A-WALL-INTR")
        line(msp, (x, n0), (x, n1), "A-WALL-INTR")
        k += 1
    label(msp, "RETAIL 10m UNITS", ((STREET_X0 + STREET_X1) / 2, (s0 + s1) / 2), height=2500)
    label(msp, "RETAIL 10m UNITS", ((STREET_X0 + STREET_X1) / 2, (n0 + n1) / 2), height=2500)

    bs0, bs1 = s0 - BOH, s0
    bn0, bn1 = n1, n1 + BOH
    wall(msp, [(STREET_X0, bs0), (STREET_X1, bs0)], layer="A-WALL-INTR")
    wall(msp, [(STREET_X0, bn1), (STREET_X1, bn1)], layer="A-WALL-INTR")
    label(msp, "BOH CORRIDOR", ((STREET_X0 + STREET_X1) / 2, (bs0 + bs1) / 2), height=2000)
    label(msp, "BOH CORRIDOR", ((STREET_X0 + STREET_X1) / 2, (bn0 + bn1) / 2), height=2000)

    wall(msp, [(STREET_X0, 0), (STREET_X0, D)], layer="A-WALL-INTR")
    wall(msp, [(STREET_X1, 0), (STREET_X1, D)], layer="A-WALL-INTR")
    label(msp, "ANCHOR STORE", (STREET_X0 / 2, 15000), height=2800)
    label(msp, "ANCHOR STORE", ((W + STREET_X1) / 2, 15000), height=2800)

    for side_y0, side_y1, name in ((0.0, bs0, "SOUTH RETAIL"), (bn1, D, "NORTH RETAIL")):
        x = STREET_X0
        while x < STREET_X1:
            line(msp, (x, side_y0), (x, side_y1), "A-WALL-INTR")
            x += SHOP_W
        line(msp, (STREET_X1, side_y0), (STREET_X1, side_y1), "A-WALL-INTR")
        label(msp, name, ((STREET_X0 + STREET_X1) / 2, (side_y0 + side_y1) / 2), height=2500)

    x = STREET_X0
    while x <= STREET_X1:
        for y in (sy0, sy1):
            rect(msp, x - 300, y - 300, x + 300, y + 300, "A-COLS")
        x += SHOP_W

    core(msp, 55000, 50000, 10000, 4000, "ESC")
    core(msp, 95000, 50000, 10000, 4000, "ESC")
    core(msp, 40000, 25000, 8000, 5600, "CORE")
    core(msp, 110000, 75000, 8000, 5600, "CORE")

    label(msp, "SHOPPING MALL L1  150m x 100m", (W / 2, D + 9000), height=5000)
    return doc
