"""
01_skeleton.py — Project skeleton: file + project + units + context + spatial tree.

The mandatory foundation. No element or geometry may exist without this.
Run: python 01_skeleton.py
"""

import ifcopenshell
import ifcopenshell.api


def build_skeleton():
    model = ifcopenshell.api.run("project.create_file")
    project = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcProject", name="My Project")
    ifcopenshell.api.run("unit.assign_unit", model)

    model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model,
        context_type="Model", context_identifier="Body",
        target_view="MODEL_VIEW", parent=model3d)

    site = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcSite", name="My Site")
    building = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcBuilding", name="Building A")
    storey = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcBuildingStorey", name="Ground Floor")

    ifcopenshell.api.run("aggregate.assign_object", model,
        relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model,
        relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", model,
        relating_object=building, products=[storey])

    return model, body, storey


if __name__ == "__main__":
    model, body, storey = build_skeleton()
    print("entities:", len(model.by_type("IfcRoot")))
    print("storeys:", [s.Name for s in model.by_type("IfcBuildingStorey")])
    print("aggregates:", len(model.by_type("IfcRelAggregates")))
