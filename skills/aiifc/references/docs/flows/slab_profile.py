"""
03_slab_profile.py — Slab with arbitrary profile from coordinates.

Builds on 01_skeleton. Creates a 6m × 4m floor slab using arbitrary profile.
Run: python 03_slab_profile.py
"""

import numpy as np
import ifcopenshell
import ifcopenshell.api

from flows import skeleton  # reuse skeleton builder


def build_slab(model, body, storey):
    slab = ifcopenshell.api.run("root.create_entity", model,
        ifc_class="IfcSlab", predefined_type="FLOOR")

    # Arbitrary rectangular profile from coordinates (shapely-compatible)
    coords = np.array([
        [0.0, 0.0],
        [6.0, 0.0],
        [6.0, 4.0],
        [0.0, 4.0],
    ])
    profile = ifcopenshell.api.run("profile.add_arbitrary_profile", model,
        profile=coords)

    # Extrude 0.2m depth
    rep = ifcopenshell.api.run("geometry.add_profile_representation", model,
        context=body, profile=profile, depth=0.2)
    ifcopenshell.api.run("geometry.assign_representation", model,
        product=slab, representation=rep)

    ifcopenshell.api.run("geometry.edit_object_placement", model, product=slab)
    ifcopenshell.api.run("spatial.assign_container", model,
        relating_structure=storey, products=[slab])

    return slab


if __name__ == "__main__":
    model, body, storey = skeleton.build_skeleton()
    slab = build_slab(model, body, storey)

    print("slab guid:", slab.GlobalId)
    print("slab type:", slab.PredefinedType)
    print("slabs:", len(model.by_type("IfcSlab")))
    print("profiles:", len(model.by_type("IfcArbitraryClosedProfileDef")))
