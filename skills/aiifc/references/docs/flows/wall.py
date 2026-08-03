"""
02_wall.py — Wall entity + geometry + placement + container.

Builds on 01_skeleton. Creates a 5m × 3m × 0.2m wall, positions it, places into storey.
Run: python 02_wall.py
"""

import numpy as np
import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.placement

from flows import skeleton  # reuse skeleton builder


def build_wall(model, body, storey):
    wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")

    # Placement at (2m East, 3m North)
    matrix = np.eye(4)
    matrix[0][3] = 2.0
    matrix[1][3] = 3.0
    ifcopenshell.api.run("geometry.edit_object_placement", model,
        product=wall, matrix=matrix, is_si=True)

    # Body: length=5m, height=3m, thickness=0.2m
    rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
        context=body, length=5, height=3, thickness=0.2)
    ifcopenshell.api.run("geometry.assign_representation", model,
        product=wall, representation=rep)

    # Place into storey
    ifcopenshell.api.run("spatial.assign_container", model,
        relating_structure=storey, products=[wall])

    return wall


if __name__ == "__main__":
    model, body, storey = skeleton.build_skeleton()
    wall = build_wall(model, body, storey)

    print("wall guid:", wall.GlobalId)
    print("walls:", len(model.by_type("IfcWall")))
    print("contained rels:", len(model.by_type("IfcRelContainedInSpatialStructure")))

    pos = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
    print("wall position:", round(pos[0][3], 1), round(pos[1][3], 1), round(pos[2][3], 1))
