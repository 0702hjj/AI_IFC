# Roof: Parapet

A low safety wall around a rooftop / terrace edge, preventing falls. Same axis and thickness as the exterior wall below, but only ~1.5m tall (not full storey height).

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Height | 1100–1500mm | 1500mm | fall-protection code ≥1100mm |
| Thickness | = exterior wall t | 280mm | reuse the wall section below |
| Base | top-storey slab top | — | rises from the terrace floor |
| Coping | optional | — | metal / precast cap on top |

## Technical Mapping

| Component | IFC class | Geometry | Note |
|---|---|---|---|
| Parapet wall | `IfcWall` | `add_wall_representation` (length × ~1.5m × t) | same axis as wall below |
| Coping | `IfcCovering` / `IfcPlate` | thin cap profile | optional top finish |

**Key point**: a parapet is **not** a full wall. Reuse the exterior wall's axis and thickness (`wall_matrix` with the `-t/2` offset), but set `height ≈ 1.5m` instead of the storey height. The rooftop stays open (terrace feel) while the edge is protected.

## Example Code

```python
import numpy as np
# Parapet: same axis + thickness as the exterior wall below, but only ~1.5m tall.
for w in exterior_walls:                        # exterior walls on the top storey
    (x1, y1), (x2, y2) = w["axis"][0], w["axis"][-1]
    t = w["t"] * 0.001                          # wall thickness (m)
    wall = api("root.create_entity", model, ifc_class="IfcWall", name=f"Parapet-{w['id']}")
    mtx, phi = wall_matrix(x1, y1, x2, y2, t, e_top)   # same axis, offset -t/2
    api("geometry.edit_object_placement", model, product=wall, matrix=mtx, is_si=True)
    L = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    rep = api("geometry.add_wall_representation", model, context=body,
              length=L, height=1.5, thickness=t)        # h=1.5m, NOT full storey height
    api("geometry.assign_representation", model, product=wall, representation=rep)
    api("spatial.assign_container", model, relating_structure=storey, products=[wall])
```

## Variations

- **Solid parapet** — masonry/concrete dwarf wall (most common).
- **Parapet + railing** — low wall topped with a metal/glass railing for extra height.
- **Glass balustrade** — frameless glass panel instead of a solid wall (modern terrace).
