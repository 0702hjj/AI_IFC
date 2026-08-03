"""Smoke test: minimal IFC (skeleton + one wall) -> viewer/data/staging/smoke-test.ifc"""
import os
import ifcopenshell
import ifcopenshell.api

OUT = os.path.join(os.path.dirname(__file__), "..", "viewer", "data", "staging", "smoke-test.ifc")
OUT = os.path.abspath(OUT)

# --- Skeleton first: Project -> Site -> Building -> Storey ---
model = ifcopenshell.api.run("project.create_file")
project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
ifcopenshell.api.run("unit.assign_unit", model)
model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
body = ifcopenshell.api.run("context.add_context", model, context_type="Model",
                            context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)
site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite")
building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding")
storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey")
storey.Elevation = 0.0
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

# --- One wall: entity -> placement -> representation -> container ---
wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall", name="SmokeWall")
ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall)
rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
                           context=body, length=5.0, height=3.0, thickness=0.2)
ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=rep)
ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
model.write(OUT)
print(f"WROTE {OUT}")

# --- Self-check 1: schema validation ---
import ifcopenshell.validate
logger = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(OUT, logger)
errors = [s for s in logger.statements]
print(f"SCHEMA_VALIDATION: {'PASS' if not errors else 'FAIL'} ({len(errors)} issue(s))")
for s in errors[:10]:
    print("  ", s)

# --- Self-check 2: reopen + structural checks ---
m2 = ifcopenshell.open(OUT)
projects = m2.by_type("IfcProject")
assert len(projects) == 1, f"expected exactly 1 IfcProject, got {len(projects)}"
print("SINGLE_PROJECT: PASS")

site2 = m2.by_type("IfcSite")
bldg2 = m2.by_type("IfcBuilding")
storey2 = m2.by_type("IfcBuildingStorey")
assert len(site2) == 1 and len(bldg2) == 1 and len(storey2) == 1, "skeleton incomplete"
print("SKELETON (Site/Building/Storey): PASS")

# every element with geometry has placement + container
walls = m2.by_type("IfcWall")
for w in walls:
    assert w.ObjectPlacement is not None, f"{w.GlobalId} missing placement"
    containers = [r.RelatingStructure for r in w.ContainedInStructure]
    assert containers, f"{w.GlobalId} missing spatial container"
    assert w.Representation is not None, f"{w.GlobalId} missing representation"
print(f"WALLS ({len(walls)}): placement+container+representation PASS")

print("SELF_CHECK: ALL PASS")
