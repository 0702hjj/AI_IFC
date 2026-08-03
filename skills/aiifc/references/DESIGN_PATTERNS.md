# Design Patterns — Architectural Design Knowledge Index

> Design knowledge distilled from generated buildings and reverse-engineered real models.
> Each pattern is parameterized and mapped to ifcopenshell.api.
> Read before choosing building massing, facade strategy, spatial organization, or component construction.
> Detailed per-pattern docs in `docs/design/` (see `docs/design/README.md` for the guided index).

---

## Mental Model

A building is **concept design**(how the whole is organized)+ **component building**(how each element is built in IFC):

```
Concept design (pick ONE per category, tune parameters in range):
  Massing (§1) → how the overall form is shaped
  Facade (§2)  → how the skin is treated
  Structure (§3) → how it stands up
  Circulation (§4) → how people move
  Spatial (§5) → how interior quality is achieved

Component building (IFC construction recipes, distilled from reverse engineering):
  Roof / Stairs / Windows / Parapet / Balcony / Mirror (§6)
```

**Composition principle**: every building needs hierarchy — base, body, top. Avoid uniform treatment.

**Material principle**: minimum 3 materials — structure, envelope, accent.

---

## Concept Design

### 1. Massing Patterns

| Pattern | Core idea | Parameters | Detail |
|---|---|---|---|
| Twisted Tower | Floor plates rotate incrementally | twist 45°–180° total | `docs/design/massing_twist.md` |
| Courtyard with Wings | Building wraps a central void | courtyard 15–40×10–30m | (to be documented) |
| Mirror Symmetry | One half mirrored across a centreline | axis, tol 150mm | `docs/design/massing_mirror.md` |

### 2. Facade Patterns

| Pattern | Core idea | Parameters | Detail |
|---|---|---|---|
| Full Glass Curtain Wall | Continuous glass, minimal frame | panel 1.2–2.0m wide | (to be documented) |
| Solid Wall + Punched Windows | Opaque wall, individual openings | window 1.2–2.4m | (to be documented) |
| Louver Facade | Tilted blades for ventilation / decoration | pitch 150–200mm, tilt 30–60° | `docs/design/windows_types.md` |

### 3. Structural Patterns

| Pattern | Core idea | Parameters | Detail |
|---|---|---|---|
| Regular Column Grid | Orthogonal columns, flat slabs | spacing 6–12m | (to be documented) |
| Concrete Core Tube | Central / peripheral core | core 8–16m, wall 0.20–0.40m | (to be documented) |

### 4. Circulation Patterns

| Pattern | Core idea | Parameters | Detail |
|---|---|---|---|
| Escalator | Inclined moving walkway | run 6–10m, incline 30°–35° | `docs/design/stairs_types.md` |
| Egress Stair (double-run) | Two runs + landing per storey | riser 150–180mm, tread 250–300mm | `docs/design/stairs_types.md` |
| Sky Bridge | Upper-floor connector | width 2.0–3.5m | (to be documented) |

### 5. Spatial Patterns

| Pattern | Core idea | Parameters | Detail |
|---|---|---|---|
| Atrium with Skylight | Central void bringing light deep | atrium 10–40×8–30m | `docs/design/spatial_atrium.md` |

## Pattern Extraction Log (concept design)

| Building | Massing | Facade | Structure | Circulation | Spatial |
|---|---|---|---|---|---|
| twist_tower | Twisted | Full glass curtain | Core tube + grid | — | — |
| shopping_mall | Box + atrium | Curtain wall | Column + beam grid | Escalator + stair | Atrium + skylight |
| highschool | Setback courtyard | Solid wall + sunshade | Grid + cores | Stair + bridge | Elliptical atrium + bridges |

## Component-Building Extraction Log (reverse-engineered real models)

| Source building | Contributed component recipes |
|---|---|
| Castle ( pitched villa / castle ) | Pitched roof (Slab ROOF + Covering + truss), dormer, combined-slope massing |
| ShangzhuLou (mall + residential) | Sawtooth stair, escalator, double-run egress stair, glass infill, louver, parapet, cantilever balcony, per-opening mirror |
| Duplex (semi-detached house) | Sawtooth stair, double-run stair, door/window reverse-mapping |

---

## Related Documents

- `docs/design/README.md` — Guided index of all per-pattern docs (concept + component)
- `SPATIAL_QUALITY.md` — Design-quality rules (checked by design_review after generation)
- `MODELING_WORKFLOWS.md` — Modeling discipline (skeleton-first / world-coords / 3-layer validation)
