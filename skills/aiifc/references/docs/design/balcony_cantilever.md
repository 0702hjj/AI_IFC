# Balcony: Cantilever Balcony

A balcony projecting outward from a facade door: a cantilever slab plus an **enclosure** that is either **open** (3-side railing) or **enclosed** (door for access + window glazing on the outer edge). Slab top is flush with the interior floor.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Projection (depth) | 1.2–1.8m | 1.5m | cantilever depth from facade |
| Slab width | door width + 2× side | door + 1.0m | side margin ≈ 0.5m each |
| Slab thickness | 120–200mm | 150mm | top flush with floor |
| Enclosure | `open` / `enclosed` | `open` | open = railing 3 sides; enclosed = door + window glazing |
| Railing height | 1.0–1.2m | 1.1m | above floor (open only) |
| Railing profile | 40×40mm | 40×40 | rectangular bar (open only) |
| Window height | 1.0–1.8m | 1.5m | enclosed: glazing sill at rail_h to rail_h+window_h |

## Technical Mapping

| Component | IFC class | Geometry | Note |
|---|---|---|---|
| Balcony slab | `IfcSlab`(FLOOR) | parametric box (`add_profile_representation`) | cantilever, top flush with floor |
| Railing (3 sides) | `IfcRailing` | 40×40 profile extruded per side | **open** enclosure: S + E + W edges |
| Door (entry) | `IfcDoor` | fills the facade opening (built by the wall-opening pipeline) | room ↔ balcony access — **always present** in both modes |
| Window (enclosed) | `IfcWindow` | glazing box on the outer S edge, sill at rail_h | **enclosed** enclosure: daylight + weather seal (replaces the S railing) |

**Key points**:
- Slab **top aligns with the interior floor** (`z_floor`), so the slab box sits at `z_floor - thickness`.
- Width is derived from the door opening: `half = door_w/2 + side_margin`. The door-centre is `wall_axis_start + along`, not the door entity's placement origin.
- **Door is always present** (room↔balcony access) — it is cut into the facade wall by the normal opening pipeline (`feature.add_feature` + `feature.add_filling`), **not** by this balcony function.
- **Open enclosure**: three railing bars (S/E/W) as `IfcRailing`, 40×40 profile per edge, at `z_floor + rail_h`.
- **Enclosed enclosure**: replace the S railing with an `IfcWindow` glazing box (sill at `z_floor + rail_h`, height = `window_h`) spanning the outer edge; keep E/W railings. This is the door+window combination.

## Example Code

```python
import numpy as np

def _bar(model, body, name, cx, cy, z, xdim_m, ydim_m, depth_m, ifc_class, predef=None):
    """Rectangular bar (railing/window share this)."""
    e = api("root.create_entity", model, ifc_class=ifc_class, name=name,
            **({"predefined_type": predef} if predef else {}))
    prof = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
                               XDim=xdim_m * 1000, YDim=ydim_m * 1000)
    rep = api("geometry.add_profile_representation", model, context=body, profile=prof, depth=depth_m)
    api("geometry.assign_representation", model, product=e, representation=rep)
    m = np.eye(4); m[0][3], m[1][3], m[2][3] = cx, cy, z
    api("geometry.edit_object_placement", model, product=e, matrix=m, is_si=True)
    return e

def balcony(name, door_x, wall_face_y, door_w, z_floor, storey,
            project=1.5, side=0.5, th=0.15, rail_h=1.1,
            enclosure="open", window_h=1.5):
    """Cantilever balcony off a facade door. Projects outward (-Y).
    enclosure: 'open' = 3-side railing; 'enclosed' = window on S edge + E/W railing.
    The door (room<->balcony) is cut into the facade wall separately by the opening pipeline."""
    half = door_w / 2 + side
    x1, x2 = door_x - half, door_x + half
    y_end = wall_face_y - project                 # outer edge (cantilever)
    depth_y = wall_face_y - y_end
    # slab (top flush with floor)
    slab = api("root.create_entity", model, ifc_class="IfcSlab",
               predefined_type="FLOOR", name=f"{name}-Slab")
    prof = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
                               XDim=(x2 - x1) * 1000, YDim=depth_y * 1000)
    rep = api("geometry.add_profile_representation", model, context=body, profile=prof, depth=th)
    api("geometry.assign_representation", model, product=slab, representation=rep)
    m = np.eye(4)
    m[0][3], m[1][3], m[2][3] = (x1+x2)/2, (y_end+wall_face_y)/2, z_floor - th
    api("geometry.edit_object_placement", model, product=slab, matrix=m, is_si=True)
    api("spatial.assign_container", model, relating_structure=storey, products=[slab])
    rh = z_floor + rail_h
    # E/W railings (both modes)
    for seg, cx, cy in (("E", x2, (y_end+wall_face_y)/2), ("W", x1, (y_end+wall_face_y)/2)):
        r = _bar(model, body, f"{name}-{seg}", cx, cy, rh, 0.04, 0.04, depth_y, "IfcRailing")
        api("spatial.assign_container", model, relating_structure=storey, products=[r])
    if enclosure == "open":
        r = _bar(model, body, f"{name}-S", (x1+x2)/2, y_end, rh, x2-x1, 0.04, 0.04, "IfcRailing")
        api("spatial.assign_container", model, relating_structure=storey, products=[r])
    else:  # enclosed: window glazing on S edge (sill at rail_h, height window_h)
        win = _bar(model, body, f"{name}-Win", (x1+x2)/2, y_end, rh,
                   x2 - x1, 0.04, window_h, "IfcWindow", predef="WINDOW")
        api("spatial.assign_container", model, relating_structure=storey, products=[win])
```

## Variations

- **Open enclosure** — 3-side railing (default; warm-climate residential, the typical 城中村 / 南方阳台).
- **Enclosed enclosure** — door (access) + window glazing on the outer edge (cold-climate / sealed balcony; the door+window combination). The door is always cut into the facade wall by the opening pipeline; the window replaces the south railing.
- **Cantilever slab** — no columns, projects from the structure (most common residential).
- **Column-supported** — balcony on brackets/columns for deeper projections.
- **Corner balcony** — wraps a building corner, railing on two outer edges.
- **Recessed (loggia)** — set into the facade instead of projecting out.
