"""
full_building.py — 完整的单层建筑(6m×4m),4面墙+1门+1窗+地板+材质颜色。

修正: 洞口完全穿透墙体厚度; 所有构件有颜色区分。
"""

from pathlib import Path
import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element
import ifcopenshell.validate

from flows.tracker import ModelStateTracker

# ── 参数 ──
WALL_T = 0.20
WALL_H = 3.0
BLDG_X = 6.0
BLDG_Y = 4.0
SLAB_T = 0.20
DOOR_W, DOOR_H = 1.0, 2.1
DOOR_OFFSET = 1.0
WIN_W, WIN_H = 1.5, 1.2
WIN_SILL = 0.9


def _add_color(model, element, r, g, b):
    """给构件的 Body 表示加一个表面颜色样式。"""
    if not element.Representation:
        return
    colour = model.create_entity("IfcColourRgb", Red=r, Green=g, Blue=b)
    rendering = model.create_entity("IfcSurfaceStyleRendering",
        SurfaceColour=colour, ReflectanceMethod="NOTDEFINED")
    surf_style = model.create_entity("IfcSurfaceStyle",
        Name="BodyColor", Side="BOTH", Styles=(rendering,))
    for rep in element.Representation.Representations:
        if rep.RepresentationIdentifier != "Body":
            continue
        for item in rep.Items:
            model.create_entity("IfcStyledItem",
                Item=item, Styles=(surf_style,))


def build_full_building():
    # ═══ ① 骨架 ═══
    model = ifcopenshell.api.run("project.create_file")
    project = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcProject", name="Demo House")
    ifcopenshell.api.run("unit.assign_unit", model)
    model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=model3d)
    site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding", name="House")
    storey = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcBuildingStorey", name="Ground Floor")
    for parent, child in [(project, site), (site, building), (building, storey)]:
        ifcopenshell.api.run("aggregate.assign_object", model,
            relating_object=parent, products=[child])
    print(f"[1] skeleton: {len(model.by_type('IfcRoot'))} entities")
    tracker = ModelStateTracker(model)
    tracker.snapshot("skeleton")

    # ═══ ② 四面墙 ═══
    def _wall(name, p1, p2):
        w = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
        rep = ifcopenshell.api.run("geometry.create_2pt_wall", model,
            element=w, context=body,
            p1=p1, p2=p2, elevation=0, height=WALL_H,
            thickness=WALL_T, is_si=True)
        ifcopenshell.api.run("geometry.assign_representation", model,
            product=w, representation=rep)
        return w

    south = _wall("south", (0, 0), (BLDG_X, 0))
    north = _wall("north", (0, BLDG_Y), (BLDG_X, BLDG_Y))
    west = _wall("west", (0, 0), (0, BLDG_Y))
    east = _wall("east", (BLDG_X, 0), (BLDG_X, BLDG_Y))
    walls = {"south": south, "north": north, "west": west, "east": east}
    ifcopenshell.api.run("spatial.assign_container", model,
        relating_structure=storey, products=list(walls.values()))
    # 墙的颜色: 暖灰
    for w in walls.values():
        _add_color(model, w, 0.72, 0.65, 0.55)
    print(f"[2] walls: 4 created")
    tracker.snapshot("walls_created")

    # ═══ ③ 地板 ═══
    slab = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcSlab", predefined_type="FLOOR")
    slab_coords = np.array([[0, 0], [BLDG_X, 0], [BLDG_X, BLDG_Y], [0, BLDG_Y]])
    slab_profile = ifcopenshell.api.run("profile.add_arbitrary_profile", model, profile=slab_coords)
    slab_rep = ifcopenshell.api.run("geometry.add_profile_representation", model,
        context=body, profile=slab_profile, depth=SLAB_T)
    ifcopenshell.api.run("geometry.assign_representation", model, product=slab, representation=slab_rep)
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=slab)
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[slab])
    _add_color(model, slab, 0.50, 0.42, 0.35)  # 棕色地板
    print(f"[3] slab: {slab.GlobalId[:8]}")
    tracker.snapshot("slab_created")

    # ═══ ④ 门(南墙 Y=0) ═══
    # 洞口定位用世界坐标(add_feature 会自动转为相对墙的坐标)
    # 南墙在 Y=0, 洞口世界 Y = 0 + offset = -0.05m
    door_opening = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcOpeningElement")
    open_rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=DOOR_W, height=DOOR_H, thickness=WALL_T * 1.5)
    ifcopenshell.api.run("geometry.assign_representation", model,
        product=door_opening, representation=open_rep)
    dm = np.eye(4)
    dm[0][3] = DOOR_OFFSET
    dm[1][3] = (WALL_T - WALL_T * 1.5) / 2  # 世界 Y = -0.05m (南墙在 Y=0)
    dm[2][3] = 0.0
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=door_opening, matrix=dm, is_si=True)
    ifcopenshell.api.run("feature.add_feature", model, feature=door_opening, element=south)

    # 门实体 + 几何 + 定位
    door = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor", predefined_type="DOOR")
    door.OverallHeight = DOOR_H * 1000
    door.OverallWidth = DOOR_W * 1000
    door_rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=DOOR_W, height=DOOR_H, thickness=0.05)
    ifcopenshell.api.run("geometry.assign_representation", model, product=door, representation=door_rep)
    # 门定位: 世界坐标(南墙在 Y=0)
    ddm = np.eye(4)
    ddm[0][3] = DOOR_OFFSET
    ddm[1][3] = 0.0
    ddm[2][3] = 0.0
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=door, matrix=ddm, is_si=True)
    ifcopenshell.api.run("feature.add_filling", model, opening=door_opening, element=door)
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[door])
    _add_color(model, door, 0.35, 0.20, 0.10)  # 深棕门
    print(f"[4] door: {door.GlobalId[:8]}")
    state = tracker.snapshot("door_created")
    assert state["doors"][0]["world_xyz_mm"][1] == 0.0, "door Y should be 0 (south wall)"
    assert state["doors"][0]["fills_opening"] is not None, "door must link to opening"

    # ═══ ⑤ 窗(北墙 Y=4m) ═══
    # 洞口定位用世界坐标: 北墙在 Y=BLDG_Y, 洞口世界 Y = BLDG_Y + offset
    win_opening = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcOpeningElement")
    wo_rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=WIN_W, height=WIN_H, thickness=WALL_T * 1.5)
    ifcopenshell.api.run("geometry.assign_representation", model,
        product=win_opening, representation=wo_rep)
    wm = np.eye(4)
    wm[0][3] = (BLDG_X - WIN_W) / 2
    wm[1][3] = BLDG_Y + (WALL_T - WALL_T * 1.5) / 2  # 世界 Y = 4.0 + (-0.05) = 3.95m
    wm[2][3] = WIN_SILL
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=win_opening, matrix=wm, is_si=True)
    ifcopenshell.api.run("feature.add_feature", model, feature=win_opening, element=north)

    # 窗实体 + 几何 + 定位
    window = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWindow", predefined_type="WINDOW")
    window.OverallHeight = WIN_H * 1000
    window.OverallWidth = WIN_W * 1000
    win_rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=WIN_W, height=WIN_H, thickness=0.05)
    ifcopenshell.api.run("geometry.assign_representation", model, product=window, representation=win_rep)
    # 窗定位: 世界坐标(北墙在 Y=4m)
    wwm = np.eye(4)
    wwm[0][3] = (BLDG_X - WIN_W) / 2
    wwm[1][3] = BLDG_Y          # 北墙 Y=4m
    wwm[2][3] = WIN_SILL
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=window, matrix=wwm, is_si=True)
    ifcopenshell.api.run("feature.add_filling", model, opening=win_opening, element=window)
    ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[window])
    _add_color(model, window, 0.60, 0.80, 0.90)  # 淡蓝窗
    print(f"[5] window: {window.GlobalId[:8]}")
    state = tracker.snapshot("window_created")
    assert state["windows"][0]["world_xyz_mm"][1] == 4000.0, "window Y should be 4000 (north wall)"
    assert state["windows"][0]["fills_opening"] is not None, "window must link to opening"

    # ═══ ⑥ 类型 + 材质 ═══
    wall_type = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcWallType", name="EXT-200", predefined_type="SOLIDWALL")
    ifcopenshell.api.run("type.assign_type", model,
        related_objects=list(walls.values()), relating_type=wall_type)
    mat_set = ifcopenshell.api.run("material.add_material_set", model,
        name="Brick+Plaster", set_type="IfcMaterialLayerSet")
    brick = ifcopenshell.api.run("material.add_material", model, name="Brick", category="masonry")
    plaster = ifcopenshell.api.run("material.add_material", model, name="Plaster", category="coating")
    lb = ifcopenshell.api.run("material.add_layer", model, layer_set=mat_set, material=brick)
    ifcopenshell.api.run("material.edit_layer", model, layer=lb, attributes={"LayerThickness": 200})
    lp = ifcopenshell.api.run("material.add_layer", model, layer_set=mat_set, material=plaster)
    ifcopenshell.api.run("material.edit_layer", model, layer=lp, attributes={"LayerThickness": 20})
    ifcopenshell.api.run("material.assign_material", model,
        products=[wall_type], type="IfcMaterialLayerSet", material=mat_set)
    print(f"[6] type+material: {wall_type.Name}")
    tracker.snapshot("type_material")

    # ═══ ⑦ 属性集 ═══
    for w in walls.values():
        ps = ifcopenshell.api.run("pset.add_pset", model, product=w, name="Pset_WallCommon")
        ifcopenshell.api.run("pset.edit_pset", model, pset=ps, properties={
            "FireRating": "REI90", "IsExternal": True, "LoadBearing": True})
    dps = ifcopenshell.api.run("pset.add_pset", model, product=door, name="Pset_DoorCommon")
    ifcopenshell.api.run("pset.edit_pset", model, pset=dps, properties={
        "FireRating": "E30", "IsExternal": True})
    wps = ifcopenshell.api.run("pset.add_pset", model, product=window, name="Pset_WindowCommon")
    ifcopenshell.api.run("pset.edit_pset", model, pset=wps, properties={
        "IsExternal": True, "GlazingAreaFraction": 0.8})
    print(f"[7] psets attached")

    # ── ⑧ 几何状态最终验证 ──
    report = tracker.check_geometry()
    if not report["validation"]["ok"]:
        for issue in report["validation"]["issues"]:
            print(f"  [ISSUE] {issue}")
    else:
        print(f"[8] tracker validation: PASS")

    return model


if __name__ == "__main__":
    model = build_full_building()
    outpath = str(Path(__file__).resolve().parents[4] / "examples" / "full_building.ifc")
    model.write(outpath)
    print(f"[8] written: {len(model.by_type('IfcRoot'))} entities → {outpath}")
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(outpath, logger)
    print("VALIDATION PASSED" if not logger.statements else f"FAILED: {len(logger.statements)} errors")
