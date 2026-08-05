import ezdxf
def gen_dxf():
    doc = ezdxf.new()
    doc.modelspace().add_circle((0, 0), 10)
    return {"document": doc}
