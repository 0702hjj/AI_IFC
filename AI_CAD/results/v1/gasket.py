import ezdxf

WIDTH = 100.0
HEIGHT = 80.0
HOLE_D = 8.0
MARGIN = 15.0

def gen_dxf():
    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    doc.layers.add("CUT", color=1)
    doc.layers.add("BEND", color=5)
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (WIDTH, 0), (WIDTH, HEIGHT), (0, HEIGHT)],
        close=True, dxfattribs={"layer": "CUT"},
    )
    for x in (MARGIN, WIDTH - MARGIN):
        for y in (MARGIN, HEIGHT - MARGIN):
            msp.add_circle((x, y), HOLE_D / 2, dxfattribs={"layer": "CUT"})
    msp.add_line((MARGIN, HEIGHT / 2), (WIDTH - MARGIN, HEIGHT / 2), dxfattribs={"layer": "BEND"})
    return doc
