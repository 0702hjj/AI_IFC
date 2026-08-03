# Roof: Pitched Roof System

Multi-layer sloped roof — the classic European pitched roof. **Do NOT use IfcRoof**: real (Revit-exported) models instead use `IfcSlab(ROOF)` + `IfcCovering` layering.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Type | gable / hip / shed / combined | gable | combined for irregular massing |
| Slope angle | 25°–45° | 35° | common in Europe |
| Ridge elevation | top storey +1.5–4m | +3m | vary across volumes |
| Eave overhang | 0.3–0.6m | 0.4m | — |
| Dormer count | 0–N | 0 | protruding windows |

## Technical Mapping

| Component | IFC class | Geometry | Role |
|---|---|---|---|
| Roof deck | `IfcSlab` (PredefinedType=ROOF) | **Brep** (sloped trapezoid) or rotated-matrix extrude | sloped structure |
| Roof tiles | `IfcCovering` (dakpan) | SweptSolid (arbitrary profile extruded along slope) | tile covering |
| Metal roof / eaves | `IfcCovering` (zinkwerk) | MappedRepresentation (typed reuse) | zinc / flashing |
| Drip edge | `IfcCovering` (waterslag) | Brep | drip strip |
| Roof truss | `IfcBeam` (halfspant) | MappedRepresentation | steel half-truss |
| Dormer | `IfcSlab` + `IfcWall` | combined Brep | protruding window |

**Key points**:
- A sloped deck **cannot** use axis-aligned extrude (`add_wall_representation`) — use a Brep (verts + faces) or a rotated matrix `M = T @ Ry(tilt) @ Rz(phi)`.
- Standardized parts (zinc, truss) use **MappedRepresentation** for reuse.
- Layering: deck (bone) → tile / metal (skin) → truss (support).

## Example Code

```python
import numpy as np
# Sloped roof deck built as Brep from precomputed verts+faces (e.g. a gable's two planes).
# boards = [{"vertices": [[x,y,z],...], "faces": [[i,j,k],...], "name": "..."}]
for b in boards:
    rep = api("geometry.add_mesh_representation", model, context=body,
              vertices=[b["vertices"]], faces=[b["faces"]], force_faceted_brep=True)
    e = api("root.create_entity", model, ifc_class="IfcSlab",
            predefined_type="ROOF", name=b["name"])
    api("geometry.assign_representation", model, product=e, representation=rep)
    api("geometry.edit_object_placement", model, product=e, matrix=np.eye(4), is_si=True)
    api("spatial.assign_container", model, relating_structure=storey, products=[e])
```

## Variations

- **Gable**: rectangular gable ends, simplest
- **Hip**: trapezoidal end slopes meeting at the ridge
- **Combined**: multiple volumes at different heights (low zone + high zone)
- **+ Dormer**: protruding window assemblies on the slope
