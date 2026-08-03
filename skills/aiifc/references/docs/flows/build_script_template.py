"""build_script_template.py — 下游构建脚本模板(features.json → IFC).

定位: 每建筑复制此模板, 读 design_builder 框定产出的 features.json, 走传统 Pipeline 生成 IFC。
复用 wall_matrix / opening_matrices(确定性展开, 不重算坐标); 构件细节(楼梯/屋顶)参考 docs/design 配方。

用法: python build_script_template.py features.json -o model.ifc
"""
import json, math, sys
from pathlib import Path
import numpy as np
import ifcopenshell, ifcopenshell.api, ifcopenshell.validate
sys.path.insert(0, str(Path(__file__).resolve().parent))
from style_color import make_style, colorize

api = ifcopenshell.api.run
MM = 0.001


def wall_matrix(x1, y1, x2, y2, t, elev):
    phi = math.atan2(y2 - y1, x2 - x1)
    c, s = math.cos(phi), math.sin(phi)
    nx, ny = -s, c
    return np.array([[c, -s, 0, x1 + nx * (-t / 2)], [s, c, 0, y1 + ny * (-t / 2)],
                     [0, 0, 1, elev], [0, 0, 0, 1.0]]), phi


def opening_matrices(x1, y1, phi, start_m, sill, fill_half, OT):
    c, s = math.cos(phi), math.sin(phi)
    nx, ny = -s, c
    def m(off):
        return np.array([[c, -s, 0, x1 + c * start_m + nx * off],
                         [s, c, 0, y1 + s * start_m + ny * off],
                         [0, 0, 1, sill], [0, 0, 0, 1.0]])
    return m(-OT / 2), m(-fill_half)


def build(features_path, out_path):
    feat = json.loads(Path(features_path).read_text())
    model = api("project.create_file")
    prj = api("root.create_entity", model, ifc_class="IfcProject", name=feat["meta"].get("name", "building"))
    api("unit.assign_unit", model)
    m3d = api("context.add_context", model, context_type="Model")
    body = api("context.add_context", model, context_identifier="Body", target_view="MODEL_VIEW", parent=m3d)
    site = api("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = api("root.create_entity", model, ifc_class="IfcBuilding", name=feat["meta"].get("name", "building"))
    api("aggregate.assign_object", model, relating_object=prj, products=[site])
    api("aggregate.assign_object", model, relating_object=site, products=[bldg])
    smap = {}
    for sn, elev in feat["storeys"].items():
        st = api("root.create_entity", model, ifc_class="IfcBuildingStorey", name=sn)
        st.Elevation = elev * 1000
        api("aggregate.assign_object", model, relating_object=bldg, products=[st])
        smap[sn] = st
    st_ext = make_style(model, "ExtWall", (0.80, 0.70, 0.55))
    st_int = make_style(model, "IntWall", (0.93, 0.93, 0.91))
    st_conc = make_style(model, "Conc", (0.62, 0.62, 0.62))
    st_glass = make_style(model, "Glass", (0.60, 0.80, 0.90), transparency=0.7)
    st_wood = make_style(model, "Wood", (0.45, 0.30, 0.15))

    walls = feat["walls"]
    selev = list(feat["storeys"].values())
    for si, (sn, elev) in enumerate(feat["storeys"].items()):
        storey = smap[sn]
        fh = (selev[si + 1] - elev) if si + 1 < len(selev) else 3.0
        winfo = {}   # walls 数组全局索引 → (ent,x1,y1,phi,t), 仅 axis 直墙(2点)可开洞
        for gi, w in enumerate(walls):
            if w["storey"] != sn:
                continue
            ax = w["axis"]; t = w.get("t", 0.2); kind = w.get("kind", "int")
            first = None
            for i in range(len(ax) - 1):
                (x1, y1), (x2, y2) = ax[i], ax[i + 1]
                L = math.hypot(x2 - x1, y2 - y1)
                if L < 1e-6:
                    continue
                wall = api("root.create_entity", model, ifc_class="IfcWall", name=f"W-{sn}-{gi}-{i}")
                mtx, phi = wall_matrix(x1, y1, x2, y2, t, elev)
                api("geometry.edit_object_placement", model, product=wall, matrix=mtx, is_si=True)
                rep = api("geometry.add_wall_representation", model, context=body, length=L, height=fh, thickness=t)
                api("geometry.assign_representation", model, product=wall, representation=rep)
                api("spatial.assign_container", model, relating_structure=storey, products=[wall])
                colorize(model, [wall], st_ext if kind == "ext" else st_int)
                if first is None:
                    first = (wall, x1, y1, phi, t)
            if len(ax) == 2 and first:
                winfo[gi] = first
        # openings(挂 axis 直墙)
        for op in [x for x in feat.get("openings", []) if x["storey"] == sn]:
            host = winfo.get(op["wall"])
            if not host:
                continue
            went, wx1, wy1, wphi, wt = host
            ow, oh = op["w"], op["h"]; sill = op.get("sill", 0.0)
            OT = max(1.6 * wt, wt + 0.2); fh2 = 0.03
            start = op["along"] - ow / 2
            om, _ = opening_matrices(wx1, wy1, wphi, start, sill + elev, fh2, OT)
            opening = api("root.create_entity", model, ifc_class="IfcOpeningElement")
            orep = api("geometry.add_wall_representation", model, context=body, length=ow, height=oh, thickness=OT)
            api("geometry.assign_representation", model, product=opening, representation=orep)
            api("geometry.edit_object_placement", model, product=opening, matrix=om, is_si=True)
            api("feature.add_feature", model, feature=opening, element=went)
            is_door = op.get("type") == "door"
            _, fm = opening_matrices(wx1, wy1, wphi, start, sill + elev, fh2, OT)
            fe = api("root.create_entity", model, ifc_class="IfcDoor" if is_door else "IfcWindow",
                     predefined_type="DOOR" if is_door else "WINDOW")
            fe.OverallWidth = op["w"] * 1000; fe.OverallHeight = op["h"] * 1000
            frep = api("geometry.add_wall_representation", model, context=body, length=ow, height=oh, thickness=2 * fh2)
            api("geometry.assign_representation", model, product=fe, representation=frep)
            api("geometry.edit_object_placement", model, product=fe, matrix=fm, is_si=True)
            api("feature.add_filling", model, opening=opening, element=fe)
            api("spatial.assign_container", model, relating_structure=storey, products=[fe])
            colorize(model, [fe], st_wood if is_door else st_glass)
        # slabs
        for s in [x for x in feat.get("slabs", []) if x["storey"] == sn]:
            prof = s.get("profile") or feat["footprint"]; t = s.get("t", 0.15)
            slab = api("root.create_entity", model, ifc_class="IfcSlab",
                       predefined_type=s.get("predef", "FLOOR"), name=f"Slab-{sn}")
            pr = api("profile.add_arbitrary_profile", model, profile=np.array([(x, y, 0.0) for x, y in prof]))
            rep = api("geometry.add_profile_representation", model, context=body, profile=pr, depth=t)
            api("geometry.assign_representation", model, product=slab, representation=rep)
            mz = np.eye(4); mz[2][3] = elev - t
            api("geometry.edit_object_placement", model, product=slab, matrix=mz, is_si=True)
            api("spatial.assign_container", model, relating_structure=storey, products=[slab])
            colorize(model, [slab], st_conc)
    model.write(out_path)
    lg = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(out_path, lg)
    ok = not lg.statements
    print(f"walls={len(model.by_type('IfcWall'))} openings={len(model.by_type('IfcOpeningElement'))} "
          f"slabs={len(model.by_type('IfcSlab'))} → {out_path} [validate {'OK' if ok else f'{len(lg.statements)} err'}]")
    return ok


if __name__ == "__main__":
    fp = sys.argv[1] if len(sys.argv) > 1 else "features.json"
    out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "model.ifc"
    sys.exit(0 if build(fp, out) else 1)
