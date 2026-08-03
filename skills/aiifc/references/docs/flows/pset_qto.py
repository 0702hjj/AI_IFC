"""
06_pset_qto.py — Property set + quantity set attachment.

Builds on 02_wall. Attaches Pset_WallCommon (designer properties)
and Qto_WallBaseQuantities (geometry-derived quantities).
Run: python 06_pset_qto.py
"""

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.util.element

from flows.skeleton import build_skeleton
from flows.wall import build_wall

# Wall dimensions (must match geometry created in 02_wall.py)
WALL_LENGTH = 5.0   # metres
WALL_HEIGHT = 3.0
WALL_THICKNESS = 0.2


def build_psets(model, wall):
    # === Pset_WallCommon (designer-specified) ===
    pset = ifcopenshell.api.run("pset.add_pset", model,
        product=wall, name="Pset_WallCommon")

    ifcopenshell.api.run("pset.edit_pset", model,
        pset=pset,
        properties={
            "FireRating": "REI90",
            "IsExternal": True,
            "LoadBearing": True,
            "AcousticRating": "42dB",
            "ThermalTransmittance": 0.35,
        })

    # === Qto_WallBaseQuantities (geometry-derived) ===
    qto = ifcopenshell.api.run("pset.add_qto", model,
        product=wall, name="Qto_WallBaseQuantities")

    ifcopenshell.api.run("pset.edit_qto", model,
        qto=qto,
        properties={
            "Length": WALL_LENGTH,
            "Width": WALL_THICKNESS,
            "Height": WALL_HEIGHT,
            "NetVolume": WALL_LENGTH * WALL_THICKNESS * WALL_HEIGHT,
            "NetSideArea": WALL_LENGTH * WALL_HEIGHT,
        })

    return pset, qto


if __name__ == "__main__":
    model, body, storey = build_skeleton()
    wall = build_wall(model, body, storey)
    pset, qto = build_psets(model, wall)

    psets = ifcopenshell.util.element.get_psets(wall)
    print("wall psets:", list(psets.keys()))
    print("FireRating:", psets.get("Pset_WallCommon", {}).get("FireRating"))
    print("IsExternal:", psets.get("Pset_WallCommon", {}).get("IsExternal"))
    print("NetVolume:", psets.get("Qto_WallBaseQuantities", {}).get("NetVolume"))
