# Doors: Door Types

Door construction distilled from real buildings + the `add_door_representation` operation_type
enum. Six families cover the common cases: **single-swing**, **double-leaf**, **sliding**,
**glass-infill**, **louvered**, **rolling-shutter**. All sit in a wall opening and attach via
filling (`feature.add_filling`). Pick the family by function (room door / grand entrance /
balcony / plant room / loading bay).

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Door width | 0.7–1.0m single / 1.4–2.4m double | 0.9m | double-leaf = 2× leaf |
| Door height | 2.0–2.4m | 2.1m | grand entrance up to 3.0m |
| Sill elevation | 0.0m (door) | 0.0m | doors are floor-level (sill=0) |
| Opening thickness | ≥1.5× wall t | 1.6× | to fully penetrate the wall |
| Leaf thickness (thin-panel fill) | 0.04–0.06m | 0.05m | glass/flush panel; parametric door uses its own lining+panel |
| Louver blade pitch | 150–200mm | 180mm | count = height / pitch (louvered door) |
| Rolling-shutter slat pitch | 100–150mm | 120mm | count = height / pitch |

## Technical Mapping

| Door type | operation_type (IfcDoor) | Geometry | Use for |
|---|---|---|---|
| Single-swing (单扇平开) | `SINGLE_SWING_LEFT` / `SINGLE_SWING_RIGHT` | parametric lining + 1 panel | room / classroom / office doors |
| Double-swing both ways | `DOUBLE_SWING_LEFT` / `DOUBLE_SWING_RIGHT` | parametric, swings both directions | café / shop / busy two-way doors |
| Double-leaf (双扇) | `DOUBLE_DOOR_SINGLE_SWING` | parametric, 2 opposing leaves | grand entrance / lobby / wide opening |
| Double-leaf both ways | `DOUBLE_DOOR_DOUBLE_SWING` | parametric, 2 leaves both ways | heavy-traffic public doors |
| Sliding (推拉) | `SLIDING_TO_LEFT` / `SLIDING_TO_RIGHT` | parametric sliding leaf | balcony / 连廊 / garden door |
| Double sliding | `DOUBLE_DOOR_SLIDING` | parametric, 2 sliding leaves | wide storefront / partition |
| Glass-infill door | `IfcDoor` + thin panel (`add_wall_representation`, th≈50mm) | flush glass panel | commercial entrance / frameless |
| Louvered door (百叶门) | `IfcDoor` shell + `IfcPlate`×n tilted blades | n tilted slats | plant room / toilet / ventilation |
| Rolling shutter (卷帘门) | `IfcDoor`(`USERDEFINED`) or `IfcBuildingElementProxy` + horizontal slat boxes | stacked thin boxes | loading bay / shopfront / garage |

## Door Families

### 1. Single-swing door (单扇平开门)
The everyday room/classroom door. Parametric `add_door_representation(operation_type=SINGLE_SWING_LEFT)`.
`LEFT`/`RIGHT` picks which side the leaf swings toward — choose so the leaf swings **into the
room** and clears the entry (GI-08 door-swing: no wall/column behind the open arc).

### 2. Double-leaf door (双扇门)
Two opposing leaves in one frame — for grand entrances, lobbies, or any opening wider than ~1.2m.
`DOUBLE_DOOR_SINGLE_SWING`. Use at the main building entrance, auditorium, or the stair-tower
external entry (GF). Overall width = 2× leaf width.

### 3. Sliding door (推拉门)
A leaf that slides parallel to the wall (no swing arc) — essential where swing clearance is
impossible: balcony, 连廊 (glazed link), garden, or wide partitions. `SLIDING_TO_LEFT`/
`SLIDING_TO_RIGHT` for one leaf; `DOUBLE_DOOR_SLIDING` for two meeting leaves. The door's
`OperationType` already encodes the slide direction, so the geometry shows the leaf offset to one
side.

### 4. Glass-infill door (无框/全玻门)
A frameless glass door — a thin glass panel (`add_wall_representation`, thickness ≈ 50mm) filling
the opening, same recipe as the window "glass infill". Used for commercial entrances, shopfronts,
and where transparency matters. Cheap to build, renders reliably.

### 5. Louvered door (百叶门)
A door shell (`IfcDoor`, filling anchor) + **n tilted `IfcPlate` blades** for ventilation —
plant rooms, toilets, utility cupboards. Same blade recipe as the window louver (stacked plates
rotated ~45°, pitch ≈180mm). Lets air through, blocks view.

### 6. Rolling shutter (卷帘门)
Horizontal-slat curtain for a loading bay / shopfront / garage. Model as stacked thin boxes
(`add_wall_representation`, each ≈ one slat pitch tall) from the lintel down, or as a single
ribbed box. Class as `IfcDoor`(`PredefinedType=USERDEFINED`, `UserDefinedType="ROLLING_SHUTTER"`)
or `IfcBuildingElementProxy`. Sits in the opening like any door.

## Opening & Filling Discipline

1. **Opening thickness ≥ 1.5× wall thickness** so the void fully penetrates.
2. **World coordinates** for the opening before `feature.add_feature` (it converts world→wall-relative automatically; never hand-set wall-local coords).
3. **Fill centering**: `add_filling` does NOT reparent the filling — its placement is manual.
   Center the door in the wall thickness:
   - thin-panel fill (glass/flush): offset = `-(panel_thickness/2)` along the wall normal;
   - parametric door (`add_door_representation`): offset by the body's thickness-direction center
     (read from the lining/panel, analogous to the window body center ≈ 0.0875m) so the frame
     nests in the wall, not floating inside the room or protruding outside.
4. **Door swing (GI-08)**: pick `LEFT`/`RIGHT` and the swing direction so no wall/column sits in
   the door's open arc; leave ≥ door-leaf-depth clearance behind the entry.

## Example Code

```python
import numpy as np, math, ifcopenshell.api
api = ifcopenshell.api.run

# --- opening (world coords) + fill matrices (host wall phi known) ---
om = mat_rz(phi, x_start, yw - OT/2, sill)        # opening matrix (OT >= 1.5*wall_t)
fm = mat_rz(phi, x_start, yw - DOOR_BODY_C/2, sill)  # fill matrix (centered)

opening = api("root.create_entity", model, ifc_class="IfcOpeningElement")
orep = api("geometry.add_wall_representation", model, context=body,
           length=w, height=h, thickness=OT)
api("geometry.assign_representation", model, product=opening, representation=orep)
api("geometry.edit_object_placement", model, product=opening, matrix=om, is_si=True)
api("feature.add_feature", model, feature=opening, element=host_wall)

# ── 1. single-swing room door (parametric) ──
door = api("root.create_entity", model, ifc_class="IfcDoor", predefined_type="DOOR",
           name="RoomDoor")
door.OverallWidth, door.OverallHeight = w*1000, h*1000
drep = api("geometry.add_door_representation", model, context=body,
           overall_height=int(h*1000), overall_width=int(w*1000),
           operation_type="SINGLE_SWING_LEFT", lining_properties=None, panel_properties=None)
api("geometry.assign_representation", model, product=door, representation=drep)
api("geometry.edit_object_placement", model, product=door, matrix=fm, is_si=True)
api("feature.add_filling", model, opening=opening, element=door)

# ── 2. double-leaf grand entrance (parametric) ──
drep = api("geometry.add_door_representation", model, context=body,
           overall_height=2400, overall_width=1800, operation_type="DOUBLE_DOOR_SINGLE_SWING",
           lining_properties=None, panel_properties=None)

# ── 3. sliding balcony door (parametric) ──
drep = api("geometry.add_door_representation", model, context=body,
           overall_height=2100, overall_width=2400, operation_type="DOUBLE_DOOR_SLIDING",
           lining_properties=None, panel_properties=None)

# ── 4. glass-infill door (thin panel, frameless) ──
glass = api("root.create_entity", model, ifc_class="IfcDoor", predefined_type="DOOR",
            name="GlassDoor")
glass.OverallWidth, glass.OverallHeight = w*1000, h*1000
grep = api("geometry.add_wall_representation", model, context=body,
           length=w, height=h, thickness=0.05)          # ~50mm glass panel
api("geometry.assign_representation", model, product=glass, representation=grep)
api("geometry.edit_object_placement", model, product=glass, matrix=fm, is_si=True)
api("feature.add_filling", model, opening=opening, element=glass)

# ── 5. rolling shutter (stacked slat boxes) ──
def rolling_shutter(opening, w, h, pitch=0.12, t=0.04):
    n = max(6, int(round(h / pitch)))
    for i in range(n):
        z = i * pitch
        slat = api("root.create_entity", model, ifc_class="IfcPlate",
                   predefined_type="USERDEFINED", name=f"Shutter-{i}")
        rep = api("geometry.add_wall_representation", model, context=body,
                  length=w, height=pitch*0.8, thickness=t)
        api("geometry.assign_representation", model, product=slat, representation=rep)
        m = fm.copy(); m[2][3] += z                      # stack downward from lintel
        api("geometry.edit_object_placement", model, product=slat, matrix=m, is_si=True)
```

## Variations

- **Single-swing** — one leaf, the standard room door (most common).
- **Double-leaf** — two leaves for grand/wide entrances (lobby, auditorium, GF stair entry).
- **Sliding** — no swing arc; balcony / 连廊 / garden / wide partition.
- **Glass-infill** — frameless thin panel; commercial entrance / shopfront.
- **Louvered** — tilted blades for ventilation (plant room / toilet).
- **Rolling shutter** — horizontal slat curtain for loading bay / garage / shopfront security.
