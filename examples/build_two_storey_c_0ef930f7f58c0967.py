"""
build_two_storey_c_0ef930f7f58c0967.py — Minimal two-storey house.

Footprint 6m x 5m, one room per floor, exterior walls + floor slabs only.
Builds on the existing skeleton file at viewer/data/staging/c_0ef930f7f58c0967.ifc
(Project + units + Model context already present).

Run: python examples/build_two_storey_c_0ef930f7f58c0967.py
"""

import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.placement

STAGING = "viewer/data/staging/c_0ef930f7f58c0967.ifc"

# Design parameters (meters, SI)
LENGTH = 6.0
WIDTH = 5.0
WALL_THICK = 0.2
WALL_HEIGHT = 3.4
SLAB_DEPTH = 0.2
STOREYS = [("Level 1", 0.0), ("Level 2", 3.4)]

# Rectangle corners (counter-clockwise) -> 4 wall segments
CORNERS = [(0.0, 0.0), (LENGTH, 0.0), (LENGTH, WIDTH), (0.0, WIDTH)]
EDGES = [(CORNERS[i], CORNERS[(i + 1) % 4]) for i in range(4)]


def get_body_context(model):
    for ctx in model.by_type("IfcGeometricRepresentationSubContext"):
        if ctx.ContextIdentifier == "Body":
            return ctx
    model3d = model.by_type("IfcGeometricRepresentationContext")[0]
    return ifcopenshell.api.run(
        "context.add_context", model, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)


def build():
    # From-zero build: fresh file (Project + units + contexts)
    model = ifcopenshell.api.run("project.create_file")
    project = ifcopenshell.api.run("root.create_entity", model,
                                   ifc_class="IfcProject", name="AI Project")
    ifcopenshell.api.run("unit.assign_unit", model,
                         length={"is_metric": True, "raw": "METERS"})
    model3d = ifcopenshell.api.run("context.add_context", model,
                                   context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=model3d)

    # --- Spatial tree: Site -> Building -> 2 Storeys ---
    site = ifcopenshell.api.run("root.create_entity", model,
                                ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", model,
                                    ifc_class="IfcBuilding", name="House")
    storeys = []
    for name, elev in STOREYS:
        st = ifcopenshell.api.run("root.create_entity", model,
                                  ifc_class="IfcBuildingStorey", name=name)
        st.Elevation = elev  # SS-03
        storeys.append(st)
    ifcopenshell.api.run("aggregate.assign_object", model,
                         relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model,
                         relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model,
                         relating_object=building, products=storeys)

    # --- Types ---
    wall_type = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcWallType", name="EXT-200", predefined_type="SOLIDWALL")
    slab_type = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcSlabType", name="SLAB-200", predefined_type="FLOOR")

    # --- Materials (layer sets on types) ---
    concrete = ifcopenshell.api.run("material.add_material", model,
                                    name="Concrete", category="concrete")
    wall_set = ifcopenshell.api.run("material.add_material_set", model,
        name="Concrete-200+Plaster", set_type="IfcMaterialLayerSet")
    layer = ifcopenshell.api.run("material.add_layer", model,
                                 layer_set=wall_set, material=concrete)
    ifcopenshell.api.run("material.edit_layer", model,
                         layer=layer, attributes={"LayerThickness": 200})
    plaster = ifcopenshell.api.run("material.add_material", model,
                                   name="Plaster", category="coating")
    layer = ifcopenshell.api.run("material.add_layer", model,
                                 layer_set=wall_set, material=plaster)
    ifcopenshell.api.run("material.edit_layer", model,
                         layer=layer, attributes={"LayerThickness": 20})
    insulation = ifcopenshell.api.run("material.add_material", model,
                                      name="Mineral Wool", category="insulation")
    ifcopenshell.api.run("material.assign_material", model,
        products=[wall_type], type="IfcMaterialLayerSet", material=wall_set)

    slab_set = ifcopenshell.api.run("material.add_material_set", model,
        name="Concrete-Slab-200+Insulation", set_type="IfcMaterialLayerSet")
    layer = ifcopenshell.api.run("material.add_layer", model,
                                 layer_set=slab_set, material=concrete)
    ifcopenshell.api.run("material.edit_layer", model,
                         layer=layer, attributes={"LayerThickness": 200})
    layer = ifcopenshell.api.run("material.add_layer", model,
                                 layer_set=slab_set, material=insulation)
    ifcopenshell.api.run("material.edit_layer", model,
                         layer=layer, attributes={"LayerThickness": 50})
    ifcopenshell.api.run("material.assign_material", model,
        products=[slab_type], type="IfcMaterialLayerSet", material=slab_set)

    # --- Elements per storey ---
    profile = ifcopenshell.api.run("profile.add_arbitrary_profile", model,
        profile=np.array([[0.0, 0.0], [LENGTH, 0.0],
                          [LENGTH, WIDTH], [0.0, WIDTH]]))

    for si, (sname, elev) in enumerate(STOREYS):
        storey = storeys[si]

        # Slab: top flush with storey elevation -> place at elev - SLAB_DEPTH
        slab = ifcopenshell.api.run("root.create_entity", model,
            ifc_class="IfcSlab", predefined_type="FLOOR",
            name=f"Slab-L{si + 1}")
        m = np.eye(4)
        m[2][3] = elev - SLAB_DEPTH  # world z
        ifcopenshell.api.run("geometry.edit_object_placement", model,
                             product=slab, matrix=m, is_si=True)
        rep = ifcopenshell.api.run("geometry.add_profile_representation", model,
                                   context=body, profile=profile, depth=SLAB_DEPTH)
        ifcopenshell.api.run("geometry.assign_representation", model,
                             product=slab, representation=rep)
        ifcopenshell.api.run("spatial.assign_container", model,
                             relating_structure=storey, products=[slab])
        ifcopenshell.api.run("type.assign_type", model,
                             related_objects=[slab], relating_type=slab_type)

        pset = ifcopenshell.api.run("pset.add_pset", model,
                                    product=slab, name="Pset_SlabCommon")
        ifcopenshell.api.run("pset.edit_pset", model, pset=pset,
                             properties={"LoadBearing": True})
        qto = ifcopenshell.api.run("pset.add_qto", model,
                                   product=slab, name="Qto_SlabBaseQuantities")
        ifcopenshell.api.run("pset.edit_qto", model, qto=qto,
            properties={"Width": SLAB_DEPTH,
                        "GrossArea": LENGTH * WIDTH,
                        "GrossVolume": LENGTH * WIDTH * SLAB_DEPTH})

        # 4 exterior walls, world elevation = storey elevation
        for wi, (p1, p2) in enumerate(EDGES):
            wall = ifcopenshell.api.run("root.create_entity", model,
                ifc_class="IfcWall", predefined_type="STANDARD",
                name=f"Wall-L{si + 1}-{wi + 1}")
            rep = ifcopenshell.api.run("geometry.create_2pt_wall", model,
                element=wall, context=body, p1=p1, p2=p2, elevation=elev,
                height=WALL_HEIGHT, thickness=WALL_THICK)
            ifcopenshell.api.run("geometry.assign_representation", model,
                                 product=wall, representation=rep)
            ifcopenshell.api.run("spatial.assign_container", model,
                                 relating_structure=storey, products=[wall])
            ifcopenshell.api.run("type.assign_type", model,
                                 related_objects=[wall], relating_type=wall_type)

            seg_len = float(np.hypot(p2[0] - p1[0], p2[1] - p1[1]))
            pset = ifcopenshell.api.run("pset.add_pset", model,
                                        product=wall, name="Pset_WallCommon")
            ifcopenshell.api.run("pset.edit_pset", model, pset=pset,
                properties={"IsExternal": True, "LoadBearing": True})
            qto = ifcopenshell.api.run("pset.add_qto", model,
                                       product=wall, name="Qto_WallBaseQuantities")
            ifcopenshell.api.run("pset.edit_qto", model, qto=qto,
                properties={"Length": seg_len,
                            "Height": WALL_HEIGHT,
                            "Width": WALL_THICK,
                            "GrossVolume": seg_len * WALL_HEIGHT * WALL_THICK})

    model.write(STAGING)
    print("walls:", len(model.by_type("IfcWall")),
          "slabs:", len(model.by_type("IfcSlab")),
          "storeys:", len(model.by_type("IfcBuildingStorey")))
    return STAGING


def self_check(path):
    """Hard-rule self check: openable, single project, skeleton, containers, placements."""
    model = ifcopenshell.open(path)
    projects = model.by_type("IfcProject")
    assert len(projects) == 1, f"expected 1 project, got {len(projects)}"
    assert len(model.by_type("IfcSite")) == 1
    assert len(model.by_type("IfcBuilding")) == 1
    assert len(model.by_type("IfcBuildingStorey")) == 2

    # every IfcWall/IfcSlab has a container and a placement
    contained = set()
    for rel in model.by_type("IfcRelContainedInSpatialStructure"):
        contained.update(rel.RelatedElements)
    for e in model.by_type("IfcWall") + model.by_type("IfcSlab"):
        assert e in contained, f"no container: {e.Name}"
        assert e.ObjectPlacement is not None, f"no placement: {e.Name}"
        assert e.Representation is not None, f"no representation: {e.Name}"

    # world-z sanity: storey elevations respected
    for slab in model.by_type("IfcSlab"):
        z = ifcopenshell.util.placement.get_local_placement(
            slab.ObjectPlacement)[2][3]
        print(f"  {slab.Name}: world z = {z:.3f}")
    for wall in model.by_type("IfcWall"):
        z = ifcopenshell.util.placement.get_local_placement(
            wall.ObjectPlacement)[2][3]
        print(f"  {wall.Name}: placement z = {z:.3f}")
    print("self-check OK")


if __name__ == "__main__":
    path = build()
    self_check(path)

    import ifcopenshell.validate
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(path, logger)
    if logger.statements:
        for s in logger.statements[:10]:
            print("VALIDATION:", s)
        raise SystemExit(f"schema validation failed: {len(logger.statements)} errors")
    print("schema validation OK ->", path)
