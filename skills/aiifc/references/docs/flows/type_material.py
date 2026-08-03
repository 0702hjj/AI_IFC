"""
05_type_material.py — Type assignment + material layer set.

Builds on 02_wall. Creates a wall type, assigns it, and attaches a material layer set.
Run: python 05_type_material.py
"""

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element

from flows.skeleton import build_skeleton
from flows.wall import build_wall


def build_type_and_material(model, wall):
    # === Wall type ===
    wall_type = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcWallType", name="EXT-200", predefined_type="SOLIDWALL")

    ifcopenshell.api.run("type.assign_type", model,
        related_objects=[wall], relating_type=wall_type)

    # === Material layer set: 200mm brick + 20mm plaster ===
    material_set = ifcopenshell.api.run("material.add_material_set", model,
        name="Brick+Plaster", set_type="IfcMaterialLayerSet")

    brick = ifcopenshell.api.run("material.add_material", model,
        name="Brick", category="masonry")
    plaster = ifcopenshell.api.run("material.add_material", model,
        name="Plaster", category="coating")

    layer_brick = ifcopenshell.api.run("material.add_layer", model,
        layer_set=material_set, material=brick)
    ifcopenshell.api.run("material.edit_layer", model,
        layer=layer_brick, attributes={"LayerThickness": 200})

    layer_plaster = ifcopenshell.api.run("material.add_layer", model,
        layer_set=material_set, material=plaster)
    ifcopenshell.api.run("material.edit_layer", model,
        layer=layer_plaster, attributes={"LayerThickness": 20})

    ifcopenshell.api.run("material.assign_material", model,
        products=[wall_type], type="IfcMaterialLayerSet", material=material_set)

    return wall_type, material_set


if __name__ == "__main__":
    model, body, storey = build_skeleton()
    wall = build_wall(model, body, storey)
    wall_type, material_set = build_type_and_material(model, wall)

    print("wall types:", len(model.by_type("IfcWallType")))
    print("materials:", [m.Name for m in model.by_type("IfcMaterial")])
    print("layer sets:", len(model.by_type("IfcMaterialLayerSet")))
    print("type of wall:", ifcopenshell.util.element.get_type(wall).Name)
