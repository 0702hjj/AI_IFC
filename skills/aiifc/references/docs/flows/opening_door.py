"""
04_opening_door.py — Opening creation + door filling.

Builds on 02_wall. Cuts a door opening in the wall, then fills it with a door.
Run: python 04_opening_door.py
"""

import numpy as np
import ifcopenshell
import ifcopenshell.api

from flows.skeleton import build_skeleton
from flows.wall import build_wall


def build_opening_and_door(model, body, storey, wall):
    door_width = 1.0    # metres
    door_height = 2.1
    wall_thickness = 0.2

    # === Phase A: Opening ===
    opening = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcOpeningElement")

    # Opening body: box matching door size × wall thickness
    opening_rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=door_width, height=door_height, thickness=wall_thickness)
    ifcopenshell.api.run("geometry.assign_representation", model,
        product=opening, representation=opening_rep)

    # Position opening: 1m along wall, centred on wall thickness, at floor
    matrix = np.eye(4)
    matrix[0][3] = 1.0
    matrix[1][3] = -wall_thickness / 2
    matrix[2][3] = 0.0
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=opening, matrix=matrix, is_si=True)

    # Cut opening into wall → IfcRelVoidsElement
    ifcopenshell.api.run("feature.add_feature", model,
        feature=opening, element=wall)

    # === Phase B: Door ===
    door = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcDoor", predefined_type="DOOR")
    door.OverallHeight = door_height * 1000  # mm (project units)
    door.OverallWidth = door_width * 1000

    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=door, matrix=matrix, is_si=True)

    # Fill opening with door → IfcRelFillsElement
    ifcopenshell.api.run("feature.add_filling", model,
        opening=opening, element=door)

    ifcopenshell.api.run("spatial.assign_container", model,
        relating_structure=storey, products=[door])

    return opening, door


if __name__ == "__main__":
    model, body, storey = build_skeleton()
    wall = build_wall(model, body, storey)
    opening, door = build_opening_and_door(model, body, storey, wall)

    print("openings:", len(model.by_type("IfcOpeningElement")))
    print("doors:", len(model.by_type("IfcDoor")))
    print("voids rel:", len(model.by_type("IfcRelVoidsElement")))
    print("fills rel:", len(model.by_type("IfcRelFillsElement")))
