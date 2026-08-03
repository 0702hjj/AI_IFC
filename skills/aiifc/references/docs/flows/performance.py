"""performance.py — 大模型性能三招(从 reverse 实战提炼).

几百构件的模型用默认逐实例操作会慢/卡。三招:
  1. **Type 级材质**: 材质 assign 到 IfcType(非每实例), 实例继承; pset 仍挂实例(viewer 可见性)
  2. **deferred container**: 累积构件 → 一次性批量建 IfcRelContainedInSpatialStructure(代替逐次 spatial.assign_container)
  3. **os._exit**: 结尾 sys.stdout.flush(); os._exit(0), 跳过 ifcopenshell 析构卡顿

用法:
    from performance import ContainerFlusher, assign_material_to_types, finish
    fl = ContainerFlusher()
    fl.defer([wall], storey)          # 代替 spatial.assign_container
    # ... 建模 ...
    fl.flush(model)                   # 一次性批量 container
    assign_material_to_types(model, {"EXT-200": "混凝土", "INT-100": "石膏板"})
    finish(0)                         # flush + os._exit
"""
import sys, os
import ifcopenshell
import ifcopenshell.api

api = ifcopenshell.api.run


# ── 1. deferred container(批量 flush) ──
class ContainerFlusher:
    """累积构件, 一次性手动建 IfcRelContainedInSpatialStructure, 代替逐次 spatial.assign_container.
    大模型下逐次 assign_container 会触发重复关系/性能开销; 累积后一次 flush 更快更干净."""

    def __init__(self):
        self.buf = {}   # storey_entity → [product, ...]

    def defer(self, products, storey):
        self.buf.setdefault(storey, []).extend(products)

    def flush(self, model):
        n = 0
        for storey, prods in self.buf.items():
            if not prods:
                continue
            model.create_entity(
                "IfcRelContainedInSpatialStructure",
                GlobalId=ifcopenshell.guid.new(),
                OwnerHistory=None, Name=None, Description=None,
                RelatedElements=list(prods),
                RelatingStructure=storey)
            n += len(prods)
        self.buf.clear()
        return n


# ── 2. Type 级材质 ──
def assign_material_to_types(model, type_to_material, category=""):
    """把材质挂到 IfcType(非每实例), 实例经 IfcRelDefinesByType 继承.
    pset 仍挂实例(属性 viewer 通常读实例, 不读 type).
    type_to_material: {IfcType实体 或 type名: 材质名}. 返回 assign 次数."""
    n = 0
    cache = {}
    for tref, matname in type_to_material.items():
        if matname not in cache:
            cache[matname] = api("material.add_material", model, name=matname, category=category or None)
        mat = cache[matname]
        t = tref if hasattr(tref, "is_a") else next(
            (x for x in model.by_type("IfcTypeProduct") if x.Name == tref), None)
        if t is None:
            continue
        api("material.assign_material", model, products=[t], material=mat)
        n += 1
    return n


# ── 3. os._exit(跳过析构卡顿) ──
def finish(code=0):
    """结尾: flush stdout 后 os._exit, 跳过 ifcopenshell/C++ 析构在大模型上的卡顿.
    在所有输出打印完后调用; 之后的清理(atExit/destructor)被跳过."""
    sys.stdout.flush()
    os._exit(code)


# ── 演示(最小端到端, 验证三招不破坏合法性) ──
if __name__ == "__main__":
    m = api("project.create_file")
    prj = api("root.create_entity", m, ifc_class="IfcProject", name="perf-demo")
    api("unit.assign_unit", m)
    m3d = api("context.add_context", m, context_type="Model")
    body = api("context.add_context", m, context_identifier="Body", target_view="MODEL_VIEW", parent=m3d)
    site = api("root.create_entity", m, ifc_class="IfcSite")
    bldg = api("root.create_entity", m, ifc_class="IfcBuilding")
    storey = api("root.create_entity", m, ifc_class="IfcBuildingStorey")
    storey.Elevation = 0.0
    api("aggregate.assign_object", m, relating_object=prj, products=[site])
    api("aggregate.assign_object", m, relating_object=site, products=[bldg])
    api("aggregate.assign_object", m, relating_object=bldg, products=[storey])

    fl = ContainerFlusher()
    for i in range(3):
        w = api("root.create_entity", m, ifc_class="IfcWall", name=f"W{i}")
        rep = api("geometry.add_wall_representation", m, context=body, length=4, height=3, thickness=0.2)
        api("geometry.assign_representation", m, product=w, representation=rep)
        api("geometry.edit_object_placement", m, product=w)
        fl.defer([w], storey)
    n = fl.flush(m)
    print(f"deferred container flush: {n} walls")

    wt = api("root.create_entity", m, ifc_class="IfcWallType", name="EXT-200")
    tn = assign_material_to_types(m, {wt: "混凝土"})
    print(f"type-level material: {tn} types")

    m.write("/tmp/perf_demo.ifc")
    import ifcopenshell.validate
    lg = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate("/tmp/perf_demo.ifc", lg)
    print(f"[validate] {'OK' if not lg.statements else f'{len(lg.statements)} errors'}")
    finish(0 if not lg.statements else 1)
