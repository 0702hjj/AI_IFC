# Design Knowledge Index

Design patterns for IFC building authoring: **concept-design modes**(how the whole building is organized)+ **component-building methods**(how specific elements are built in IFC). Distilled from reverse-engineering real buildings.

## Conventions

- **Concept design first, component building second**: decide the overall organization before component details.
- **Pick one pattern per category, tune parameters within range**: do not stack patterns; keep hierarchy (base / body / top).
- **Component methods map directly to IFC**: each pattern gives IFC class + geometry + parameter range, so the agent does not reinvent.
- **Materials ≥3**: structure / envelope / accent.
- **Keep sub-docs thin**: each pattern doc holds only a Parameters table + Technical Mapping + short Example Code + Variations; core principles live in this README.

## Recommended Reading Order

Concept design first (whole: Massing → Facade → Structure → Circulation → Spatial), then component building (details: Roof → Stairs → Windows → Parapet → Balcony → Mirror). Concept design decides "what the building looks like"; component building decides "how each element is built in IFC".

---

## 1. Concept Design Modes

How the overall building is organized — massing, facade, structure, circulation, spatial quality.

- [massing_twist](massing_twist.md) — Twisted tower: floor plates rotate per level, core stays fixed
- [spatial_atrium](spatial_atrium.md) — Atrium with skylight: central full-height void for deep daylight

## 2. Component Building Methods

How to build specific IFC components — roof, stairs, windows, parapet, balcony, mirror-massing. Each gives IFC class + geometry + parameter range.

- [roof_pitched](roof_pitched.md) — Pitched roof: IfcSlab(ROOF) + IfcCovering layering + IfcBeam truss [P0]
- [stairs_types](stairs_types.md) — Stair types: sawtooth profile / per-step boxes / steel truss / elevator shaft [P1]
- [windows_types](windows_types.md) — Window types: glass infill / louver / dormer [P1]
- [doors_types](doors_types.md) — Door types: single-swing / double-leaf / sliding / glass-infill / louvered / rolling-shutter (operation_type enum) [P1]
- [parapet](parapet.md) — Parapet: rooftop safety dwarf wall (on exterior axis, h≈1500mm) [P2]
- [balcony_cantilever](balcony_cantilever.md) — Cantilever balcony: cantilever slab + railing + door [P2]
- [massing_mirror](massing_mirror.md) — Mirror massing: whole building mirrored across an E/W axis [P2]

---

## Related Documents

- `../../DESIGN_PATTERNS.md` — Concept-design master table (Massing / Facade / Structure / Circulation / Spatial)
- `../../SPATIAL_QUALITY.md` — Design-quality rules (checked by design_review)
- `../../MODELING_WORKFLOWS.md` — Modeling discipline (skeleton-first / world-coords / 3-layer validation)
