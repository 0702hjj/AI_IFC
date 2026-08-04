"""build_skeleton.py — Minimal complete IFC model (skeleton + one wall + one slab).

Copy this template and edit. Run with a Python that has ifcopenshell installed:
    python build_skeleton.py    # writes model.ifc in the working directory
"""

import numpy as np
import ifcopenshell
import ifcopenshell.api

# Skeleton
model = ifcopenshell.api.run("project.create_file")
project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
ifcopenshell.api.run("unit.assign_unit", model)
model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
body = ifcopenshell.api.run("context.add_context", model, context_type="Model",
    context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)
site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite")
building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding")
storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey")
storey.Elevation = 0.0  # SS-03: every storey must have Elevation
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

# Wall (entity → placement → representation → container)
wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall)
rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
    context=body, length=5, height=3, thickness=0.2)
ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=rep)
ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])

# Export + validate
model.write("model.ifc")
import ifcopenshell.validate
logger = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate("model.ifc", logger)
assert not logger.statements, f"Validation failed: {logger.statements}"
