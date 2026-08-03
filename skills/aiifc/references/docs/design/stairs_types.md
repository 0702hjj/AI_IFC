# Stairs: Stair Types

Two families distilled from real buildings: **mall / core stairs**(straight sawtooth runs, incl. escalators)and **egress stairs**(residential double-run with a landing). All runs are built as independent step boxes to dodge a known tessellation bug.

**A stair's only hard requirements are connectivity + walkability** (it must reach every floor and be climbable — the connectivity block below). Everything about *form* — straight vs spiral vs cantilever, open vs enclosed shaft, railed vs railing-free — is a **design choice driven by occupancy/code context, never a mandatory checklist**. A circular bookshop's spiral stair or a private loft stair is as valid as an enclosed egress stair.

> **Schema position marking matches the stair's role** (see `DESIGN_JSON_SCHEMA` → stairs). Two forms, pick by role — don't force one template on all stairs:
> - **Enclosed / egress stairs** (`double_run`, `straight`) → `shaft:{x:[i,j],y:[k,l]}` (axis-grid indices). Shaft boundaries ARE wall axes → the stair is born hugging existing walls. The side-alignment (hug-wall) is therefore automatic for this family, and `design_review` checks it.
> - **Open stairs** (`spiral`, `cantilever`, `escalator`, open-atrium ramps) → `at:[x,y]` + `size:[w,l]` (free position). Free-standing in open space, NOT wall-bound, no shaft. `design_review`'s side-alignment check is **skipped** for these (a spiral stair in a bookshop must not be forced against a wall).
>
> **Shaft enclosure (surrounding walls / 隔板) is OPTIONAL even for egress stairs** — the shaft boundaries already are walls; adding a second thin cavity wall ("small wall inside a wall") is the GI-12 anti-pattern. Open stairs have no enclosure at all.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Riser height | 150–180mm | 167mm | `rise_total / n_risers` |
| Tread depth | 250–300mm | 260mm | per-step box run dimension |
| Storey height | 3.0–4.8m | 3.0m | `rise_total` of a full storey |
| Stair width | 1.1–1.6m | 1.2m | box width |
| Double-run split | half + half | 1.5m + 1.5m | egress: two runs + landing |

> **Mandatory: floor-to-floor connectivity — the stair MUST serve every storey (保障与外界楼层连通).**
> A stair that doesn't actually reach a floor makes that floor unreachable — a total functional
> failure ("到不了下一层"). Four conditions must ALL hold; all are verified by `design_review` GI-09:
>
> 1. **`rise_run == storey_height / 2`** — each run climbs exactly half a storey, so a full
>    double-run (R1 + landing + R2) climbs exactly one storey. Pick `n_risers` so
>    `storey_height / (2·n_risers) ∈ [150,180]mm` (3.6m→n=10/riser180; 4.5m→n=13; 5.0m→n=15).
>    A round-number `rise_run` (e.g. 1.5) for a 3.6m storey climbs only 3.0m → 0.6m short.
> 2. **R2 is the UPPER half — the #1 silent bug.** R1 steps sit at `z = z0 + j·rise` (lower half);
>    R2 steps **MUST** sit at `z = z0 + rise_run + j·rise` (upper half, starting from the landing).
>    A frequent copy-paste bug reuses `z0 + j·rise` for both runs → R2 overlaps R1 in the lower
>    half, the whole stair climbs only `rise_run` (half a storey), and **every floor above is
>    disconnected**. Always give R2 its own upper-half z. (GI-09 catches this: the highest tread
>    tops out at `z0+rise_run`, flagged `Xmm below next floor`.)
> 3. **Landing flush** — landing top `z0 + rise_run` == R1 last-tread top == R2 first-tread base
>    (±25mm); the landing must actually bridge the two runs (no floating landing, no gap).
> 4. **Arrival = next floor + horizontal exit at every floor** — R2 last-tread top
>    `z0 + 2·rise_run` == next-storey elevation (±100mm); AND every occupied floor's slab carries
>    a shaft opening (Method-A void or `IfcOpeningElement`) aligned over the run lane, with a
>    door/opening from the stair onto that floor, so you can step off at each level. The **top
>    floor has no outgoing flight** — build no stair there, and the roof/RF slab caps the shaft
>    (else GI-03 flags a flight piercing a solid roof).

> **Fall protection is contextual, not absolute (no mandatory railing / partition / enclosure).**
> A double-run stair has an open well between the two parallel lanes. **When the stair serves
> multiple households or public/occupied floors**, add a sloped `IfcRailing` on the well edge and
> enclose the shaft (shaft walls + door) so occupants don't step off into the void. **But this is
> NOT a universal rule** — a private single-dwelling stair, an open gallery/bookshop stair, a
> spiral or cantilever stair, or a low-occupancy service stair may legitimately have no railing,
> no shaft partition, and no enclosure. Guarding is a **design choice by occupancy + code
> context**, not a blanket requirement. (If you do enclose, see `add_stair_railing` + shaft walls
> in the example below — one pattern, not the only valid one.)

> **Size the stair, don't build thin cavity walls (anti-pattern).**
> In the design JSON the shaft is given as **axis_grid indices** (`shaft:{x:[i,j], y:[k,l]}`),
> so the shaft rectangle boundaries ARE wall axes — the stair is born hugging existing walls,
> no separate "align" step. **Do NOT** then erect a new thin wall ~1m away from an existing wall
> to "enclose" the shaft — that creates a useless cavity ("small wall inside a wall"). If you
> enclose the shaft (optional, see fall protection above), its side boundaries are the shaft-
> rectangle edges (= existing walls on those axes) OR a single shaft wall at the full stair-width
> distance — never a second wall hugging an existing one. The stair itself fills its shaft
> rectangle; adjust the **stair's** dimensions within the shaft, don't pile on extra walls.

> **Keep a circulation path — the stair must not block the corridor/连廊 (anti-pattern).**
> A stair shaft that fills the whole end-bay blocks horizontal circulation between the corridor
> and any sky-bridge/连廊. Reserve a solid-floor strip beside the shaft (e.g. shaft `[32,35]` +
> 2m circulation strip `[35,37]`) so occupants can pass the stair at every floor. The stair is
> for vertical travel; the strip is for horizontal travel — they coexist without blocking.

> **Egress entry is contextual (public fire-egress vs private stair).**
> A **public egress stair** (multi-tenant / fire escape) must be reachable from external circulation and serve every floor: put its entry/exit door on the **corridor facade** at each storey, with a solid-floor vestibule behind it leading to the first tread — pattern `outside → corridor → entry door → vestibule → R1`, and reverse per floor (`R2 arrival → vestibule → entry door → corridor`). Never bury it behind a separate lobby door; and at the ground floor open a dedicated door straight to the outside.
> A **private / internal / service stair** (single dwelling, duplex, loft) needs none of this — it can open directly into a living space, with no corridor door and no dedicated outdoor door. Match the entry pattern to the stair's role; don't impose the fire-egress template on every stair.

## Technical Mapping

| Component | IFC class | Geometry | Note |
|---|---|---|---|
| Straight run | `IfcStairFlight`(STRAIGHT) | n independent step boxes (`add_wall_representation`) | sawtooth run |
| Landing | `IfcSlab`(LANDING) | parametric box (`add_profile_representation`) | between runs |
| Escalator | `IfcBuildingElementProxy` | step boxes, shallow incline (n≈26, tread=run/26) | mall escalator |
| Stair-shaft cap | `IfcSlab`(ROOF) | parametric box | top-floor cap |
| Shaft opening | `IfcOpeningElement` | arbitrary-profile extrude, depth > slab thickness | penetrates slab |

**Critical bug workaround**: `add_profile_representation` on `IfcStairFlight` has a tessellation bug (one extra vertex at the origin). Build **each step as its own box** with `add_wall_representation` (pure translation, no rotation). Do NOT extrude a sawtooth profile for the flight.

## Stair Families

### 1. Mall / core straight run (sawtooth_run)
- One flight = n independent step boxes, pure translation (no rotation).
- Start convention per direction: `+Y`=(west x, south y, z0); `-Y`=(west x, north y, z0); `+X`=(west x, south y, z0); `-X`=(east x, south y, z0).
- Step box `length`/`thickness` swap with direction (an X-run uses length=tread, thickness=width).

### 2. Egress double-run (res_stair)
- R1 (+Y, 9 risers, 1.5m) → landing (top at z0+1.5m) → R2 (-Y, 9 risers, 1.5m) = full 3.0m storey.
- **Continuity is mandatory** (the root cause of "disconnected stairs"): the landing top must sit at exactly `z0+1.5` (flush with R1's last tread top and R2's first tread bottom), and **R2 must start at the landing's south edge** — never at the shaft north wall. Coordinate relation (shaft Y∈[a,b], tread=0.26, 9 risers):
  - R1: `y ∈ [a, a+9·0.26]` (= `[a, a+2.34]`), z `z0 → z0+1.5`
  - landing: `y ∈ [a+9·0.26−0.26, b]` (= `[a+2.08, b]`), top = `z0+1.5`
  - R2: starts at `(x_east, a+2.08, z0+1.5)`, `-Y` → `y ∈ [a+2.08, a−0.26]`, z `z0+1.5 → z0+3.0`
- The shaft covers R1 + landing + R2; egress doors sit at the shaft.

### 3. Escalator (mall)
- `sawtooth_run` with `ifc_class="IfcBuildingElementProxy"`, shallow incline (many small risers, tread = run/26).

## Slab Configuration (how to open the slab for a stair)

A stair/escalator shaft that **penetrates a slab** must be cut through that slab (straight flights only — spiral / cantilever / non-piercing stairs need no hole, per SPATIAL_QUALITY GI-03). Two methods — **prefer A** (one-shot, no boolean-order issues; this is what rebuild_mall residential uses):

**Method A — profile inner hole (recommended, `IfcArbitraryProfileDefWithVoids`)**: build the slab's footprint profile WITH the shaft as an inner curve (hole). The slab is *born* with the hole — no separate opening, no boolean, no penetration-depth guessing. Best when shafts are known at slab-build time (forward generation, regular grids).

**Method B — `IfcOpeningElement` + `feature.add_feature` (post-hoc)**: cut an already-existing slab. Use only when the slab already exists (reverse engineering, late-added shafts).
1. **Penetration rule** — `feature.add_feature`: `IfcOpeningElement` → slab.
2. **Opening geometry** — arbitrary-profile extrude with `depth` (e.g. 0.45m) **greater than slab thickness** (0.15m) so it fully penetrates; place it centred through the slab at `z0 - (depth - slab_th)/2`.
3. **Alignment** — align the shaft opening to the run lane. For a **double-run** stair the opening **alternates between floors** (arrival lane on one floor, departure lane on the next), and extends ~300mm past the last tread box.
4. **Top floor** — for a straight through-stair, cap the shaft with a roof slab (`IfcSlab`, PredefinedType=ROOF) instead of an opening (else GI-03 flags a flight piercing the roof).
5. **Escalator well** — also cut an escalator shaft through each mall floor.

## Example Code

```python
import numpy as np

# --- straight run: n independent step boxes (avoids IfcStairFlight tessellation bug) ---
def sawtooth_run(name, start, direction, n_risers, tread, rise_total, width, storey):
    rise = rise_total / n_risers
    sx, sy, sz = start
    x_run = direction in ("+X", "-X")
    L, T = (tread, width) if x_run else (width, tread)   # swap with direction
    for j in range(n_risers):
        z = sz + j * rise
        if   direction == "+Y": ox, oy = sx, sy + j * tread
        elif direction == "-Y": ox, oy = sx, sy - (j + 1) * tread
        elif direction == "+X": ox, oy = sx + j * tread, sy
        else:                   ox, oy = sx - (j + 1) * tread, sy
        step = api("root.create_entity", model, ifc_class="IfcStairFlight",
                   name=f"{name}-S{j+1}", predefined_type="STRAIGHT")
        rep = api("geometry.add_wall_representation", model, context=body,
                  length=L, height=rise, thickness=T)
        api("geometry.assign_representation", model, product=step, representation=rep)
        m = np.eye(4); m[0][3], m[1][3], m[2][3] = ox, oy, z
        api("geometry.edit_object_placement", model, product=step, matrix=m, is_si=True)
        api("spatial.assign_container", model, relating_structure=storey, products=[step])

# --- egress double-run: R1 + landing + R2 = full storey (shaft Y∈[a,b]) ---
n, tread, rise_run = 9, 0.26, 1.5
sawtooth_run("R1", (x_west, a, z0), "+Y", n, tread, rise_run, width, storey)   # y a→a+2.34
# landing: top flush z0+1.5; spans R1-top edge to shaft north wall, across both runs
land_y0 = a + n * tread - tread        # = a+2.08  ← R2 must start HERE (continuity)
landing("L", x_west, land_y0, x_east, b, z0 + rise_run, storey)                # IfcSlab(LANDING)
sawtooth_run("R2", (x_east, land_y0, z0 + rise_run), "-Y", n, tread, rise_run, width, storey)

# --- Method A (recommended): slab born with shaft hole — IfcArbitraryProfileDefWithVoids ---
# 单位: 手动 create_entity 的 IfcCartesianPoint 用模型单位(mm); FP/shaft 若是 m 必须 ×1000!
# (api profile.add_arbitrary_profile 内部转 mm, 但手动 create_entity 不转 — 漏转会建出 24mm 微型板)
ext_pts = [model.create_entity("IfcCartesianPoint", Coordinates=(float(x)*1000, float(y)*1000))
           for x, y in FP_OUTLINE]
ext_line = model.create_entity("IfcPolyline", Points=ext_pts)
inner = []
for (sx0, sy0, sx1, sy1) in SHAFT_RECTS:                       # shaft = (x0,y0,x1,y1)
    h_pts = [model.create_entity("IfcCartesianPoint", Coordinates=(float(p[0])*1000, float(p[1])*1000))
             for p in [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]]
    inner.append(model.create_entity("IfcPolyline", Points=h_pts))
prof = model.create_entity("IfcArbitraryProfileDefWithVoids", ProfileType="AREA",
                           OuterCurve=ext_line, InnerCurves=inner)
rep = api("geometry.add_profile_representation", model, context=body, profile=prof, depth=0.15)
# (assign_representation + place at z0 → slab now has the shaft hole natively)

# --- Method B (post-hoc, only if slab already exists) ---
# 单位: api profile.add_arbitrary_profile 内部转 mm (传 m 即可) — 与 Method A 手动版不同
op = api("root.create_entity", model, ifc_class="IfcOpeningElement", name="StairShaft")
prof = api("profile.add_arbitrary_profile", model,
           profile=np.array([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]))  # 传 m, API 转 mm
rep = api("geometry.add_profile_representation", model, context=body, profile=prof, depth=0.45)
api("geometry.assign_representation", model, product=op, representation=rep)
m = np.eye(4); m[2][3] = z0 - 0.15   # centred through the slab
api("geometry.edit_object_placement", model, product=op, matrix=m, is_si=True)
api("feature.add_feature", model, feature=op, element=slab)

# --- [可选] sloped guardrail along a run's inner (well) edge + shaft enclosure (fall protection, 仅公共/多户需防护时) ---
def add_stair_railing(name, xw, y_start, y_end, z_low, z_high, storey, rail_type, body, RAIL_H=1.1):
    """斜向围栏:local X(长)→沿坡, local Y(厚)→世界 -X, local Z(高)→坡法向(竖向净高 RAIL_H)。"""
    dy, dz = y_end - y_start, z_high - z_low
    L = math.hypot(dy, dz)
    cosp, sinp = dy / L, dz / L
    bh = RAIL_H / cosp if abs(cosp) > 1e-3 else RAIL_H      # 板高 → 竖向净高 = RAIL_H
    rail = api("root.create_entity", model, ifc_class="IfcRailing", name=name)
    rep = api("geometry.add_wall_representation", model, context=body, length=L, height=bh, thickness=0.06)
    api("geometry.assign_representation", model, product=rail, representation=rep)
    M = np.array([[0, -1, 0, xw + 0.03], [cosp, 0, -sinp, y_start],
                  [sinp, 0, cosp, z_low], [0, 0, 0, 1.0]])
    api("geometry.edit_object_placement", model, product=rail, matrix=M, is_si=True)
    api("spatial.assign_container", model, relating_structure=storey, products=[rail])
    api("type.assign_type", model, related_objects=[rail], relating_type=rail_type)

# [可选 — 仅公共/多户需防坠落时] 井道侧(内缘)加围栏; 梯井洞可用墙+门围合
# 单户 / 开敞 / 旋转 / 悬挑楼梯可全部省略 (多样性, 无强制隔板/栏杆/围合)
# add_stair_railing("R1Rail", lane_w + width, y_a, y_a + n * tread, z0, z0 + rise_run, storey, ...)
# add_stair_railing("R2Rail", lane_e,        y_land, y_a, z0 + rise_run, z0 + 2 * rise_run, storey, ...)
# 梯井围合墙(西/北/南+入口门) —— 仅在需要封闭核心筒时; 开敞楼梯/环形书屋楼梯不设
```

## Variations

- **Straight run** — single flight between storeys (mall / core).
- **Double-run with landing** — two opposing runs + landing, the standard egress stair.
- **Escalator** — shallow-incline step boxes as `IfcBuildingElementProxy`.
- **Stair-shaft cap** — top floor closes the shaft with an `IfcSlab`(ROOF) instead of an opening.
