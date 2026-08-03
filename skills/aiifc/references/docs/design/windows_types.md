# Windows: Window Types

Window construction distilled from real buildings: **standard glazed windows**, **glass infill** for empty openings, **louvers** (ventilation/decoration), and **dormers** protruding from roof slopes. All sit in a wall/roof opening and are attached via filling.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Window width | 0.9–3.0m | 1.5m | louver/large up to 9m |
| Window height | 1.2–2.4m | 1.8m | full-height up to 7.7m |
| Sill elevation | 0.9–1.1m | 0.9m | above storey floor |
| Opening thickness | ≥1.5× wall t | 1.6× | to fully penetrate |
| Louver blade pitch | 150–200mm | 180mm | count = height / pitch |
| Louver blade angle | 30°–60° | 45° | rain-shedding tilt |
| Frame face width | 50–80mm | 60mm | framed-window border bar face |
| Frame depth | 60–100mm | 80mm | framed-window bar depth into wall |
| Mullion/transom count | 1–4 each | 1+1 | framed-window grid (cols×rows panes) |

## Technical Mapping

| Window type | IFC class | Geometry | Note |
|---|---|---|---|
| Standard window | `IfcWindow` | `add_window_representation` (frame + sashes) | parametric |
| Framed window (带框分格窗) | `IfcMember`×(frame+mullions+transoms) + `IfcPlate`×panes | thin positioned boxes | premium commercial/residential |
| Glass infill | `IfcWindow` | thin panel (`add_wall_representation`, th≈60mm) | fills an empty opening |
| Louver | `IfcWindow`(shell) + `IfcPlate`×n | n tilted blades (Rx rotation) | ventilation / decoration |
| Dormer | `IfcSlab` + `IfcWall` | combined Brep | protrudes from roof slope |

## Window Families

### 1. Standard glazed window
Parametric `add_window_representation` (lining + panels). Use for ordinary punched windows.

### 2. Framed window / 带框分格窗 (premium commercial & residential)
The "精品商品楼" look: a visible **outer frame** (head + sill + two jambs) plus **mullions** (vertical
bars 中竖框) and **transoms** (horizontal bars 中横档) dividing the glass into a grid of panes —
what the parametric `add_window_representation` cannot do beyond simple 2/3 splits. Build it as a
**multi-element assembly**: each frame bar / mullion / transom is an `IfcMember` thin box, each
glass pane an `IfcPlate`, all placed via `edit_object_placement` in the wall opening (the
curtain-wall / storefront pattern). Parameters: frame face `FW`≈60mm, frame depth `FD`≈80mm,
`cols`/`rows` mullions/transoms, pane thickness `PT`≈20mm. Center the assembly in the wall
thickness. See example code below.

### 3. Glass infill (empty opening → thin panel)
When an opening has no fill (curtain-wall bay, glass panel slot), fill it with a **thin glass panel** (`add_wall_representation`, thickness ≈ 60mm) instead of leaving a hole. Rule: every opening should be filled.

### 4. Louver (ventilation / decorative slats)
An `IfcWindow` **shell** (filling anchor, no panel geometry) + **n tilted `IfcPlate` blades**. Blades are thin plates rotated about the horizontal axis by `ang` (45°), stacked vertically with pitch ≈ 180mm (count auto-derived from height). Placement matrix chain `m_world = fm @ T @ Rx`, where `fm` is the fill matrix (opening-local: X=window width, Y=wall normal, Z=vertical, origin=lower-left sill).

### 5. Dormer (roof window)
A small assembly protruding from a roof slope: `IfcSlab` + `IfcWall` as a **combined Brep** (non-extrudable sloped geometry).

## Opening & Filling Discipline

1. **Opening thickness ≥ 1.5× wall thickness** so the void fully penetrates.
2. **World coordinates** for the opening before `feature.add_feature` (it converts world→wall-relative automatically; never hand-set wall-local coords).
3. **Fill centreing**: `f_start = start_m + (ow - fw)/2` so the fill is centred in the opening.
4. **Auto-fill decision** for an empty opening:
   - ~913×2125 → elevator door (`IfcDoor` 900×2100, centred)
   - otherwise → glass infill (`IfcWindow` thin panel)
   - name/type contains "louver" (or width > 3000mm) → **louver**, not a pedestrian door.

## Example Code

```python
import numpy as np, math

# --- opening + glass infill ---
om, fm = opening_matrices(wx1, wy1, wphi, start_m, sill_abs, fill_half, OT)  # world coords
opening = api("root.create_entity", model, ifc_class="IfcOpeningElement")
orep = api("geometry.add_wall_representation", model, context=body,
           length=ow, height=oh, thickness=OT)            # OT >= 1.5 * wall_t
api("geometry.assign_representation", model, product=opening, representation=orep)
api("geometry.edit_object_placement", model, product=opening, matrix=om, is_si=True)
api("feature.add_feature", model, feature=opening, element=wall)

win = api("root.create_entity", model, ifc_class="IfcWindow",
          predefined_type="WINDOW", name="GlassFill")
wrep = api("geometry.add_wall_representation", model, context=body,
           length=ow, height=oh, thickness=0.06)          # thin glass panel ~60mm
api("geometry.assign_representation", model, product=win, representation=wrep)
api("geometry.edit_object_placement", model, product=win, matrix=fm, is_si=True)
api("feature.add_filling", model, opening=opening, element=win)

# --- louver: window shell + n tilted plate blades ---
def louver_blades(fm, fw, fh, n=None, bt=0.03, bd=0.2, ang=45):
    n = n or max(6, int(round(fh / 0.18)))
    pitch, rad = fh / n, math.radians(ang)
    ca, sa = math.cos(rad), math.sin(rad)
    Rx = np.array([[1,0,0,0],[0,ca,-sa,0],[0,sa,ca,0],[0,0,0,1.0]])
    for i in range(n):
        zc = (i + 0.5) * pitch                  # blade centre height (opening-local)
        cy = ca*bd/2 - sa*bt/2                  # centre offset after Rx (Y)
        cz = sa*bd/2 + ca*bt/2                  # centre offset after Rx (Z)
        T = np.array([[1,0,0,0],[0,1,0,-cy],[0,0,1,zc-cz],[0,0,0,1.0]])
        b = api("root.create_entity", model, ifc_class="IfcPlate",
                predefined_type="USERDEFINED", name=f"Louver-{i}")
        rep = api("geometry.add_wall_representation", model, context=body,
                  length=fw, height=bt, thickness=bd)
        api("geometry.assign_representation", model, product=b, representation=rep)
        api("geometry.edit_object_placement", model, product=b, matrix=fm @ T @ Rx, is_si=True)

# --- framed window (带框分格窗): IfcMember bars + IfcPlate panes, each placed in the opening ---
#   wall is phi=0, centered on Y=0; opening already cut at world (ox, oy, sill) size W×H.
def framed_window(ox, oy, sill, W, H, wall_t, cols=2, rows=2, FW=0.06, FD=0.08, PT=0.02, storey=st):
    def box(cls, name, x, y, z, w, d, h):           # box [x,x+w]×[y,y+d]×[z,z+h]
        e = api("root.create_entity", model, ifc_class=cls, name=name)
        rep = api("geometry.add_wall_representation", model, context=body,
                  length=w, height=h, thickness=d)   # X=length, Y=thickness(into wall), Z=height
        api("geometry.assign_representation", model, product=e, representation=rep)
        api("geometry.edit_object_placement", model, product=e, matrix=mat_rz(0, x, y, z), is_si=True)
        api("spatial.assign_container", model, relating_structure=storey, products=[e])
        return e
    y0 = oy + (wall_t - FD) / 2                       # centre frame depth in wall thickness
    gpy = oy + (wall_t - PT) / 2                       # centre pane in wall thickness
    # outer frame: head + sill + two jambs
    box("IfcMember", "head", ox, y0, sill + H - FW, W, FD, FW)
    box("IfcMember", "sill", ox, y0, sill, W, FD, FW)
    box("IfcMember", "jamb-L", ox, y0, sill + FW, FW, FD, H - 2 * FW)
    box("IfcMember", "jamb-R", ox + W - FW, y0, sill + FW, FW, FD, H - 2 * FW)
    # mullions (vertical) + transoms (horizontal) → cols×rows pane grid
    cw = (W - (cols + 1) * FW) / cols                  # pane width per column
    ch = (H - (rows + 1) * FW) / rows                  # pane height per row
    for c in range(1, cols):
        box("IfcMember", f"mul-{c}", ox + c * (cw + FW), y0, sill + FW, FW, FD, H - 2 * FW)
    for r in range(1, rows):
        box("IfcMember", f"trn-{r}", ox + FW, y0, sill + r * (ch + FW), W - 2 * FW, FD, FW)
    # glass panes, one per cell
    for c in range(cols):
        for r in range(rows):
            box("IfcPlate", f"pane-{c}{r}",
                ox + FW + c * (cw + FW), gpy, sill + FW + r * (ch + FW), cw, PT, ch)
```

## Variations

- **Standard window** — parametric frame + sashes for ordinary punched windows.
- **Framed window (带框分格窗)** — outer frame + mullion/transom grid + glass panes (IfcMember + IfcPlate); premium commercial / residential storefronts.
- **Glass infill** — thin glass panel filling an otherwise empty opening (curtain bays, slots).
- **Louver** — tilted `IfcPlate` blades for ventilation / decorative facades (incl. large facade louvers).
- **Dormer** — protruding roof-window assembly as a combined `IfcSlab`+`IfcWall` Brep.
