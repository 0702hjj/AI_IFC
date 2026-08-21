# consume_upstream/ —— cad->ifc consume-upstream parse references (filled in P2)

> This directory backs stage ② (parse & consume) of `workflows/CONSUME_UPSTREAM.md` — the parse rules
> and mapping tables for turning bim_supplement / building.json / DXF into an IFC build script.
> **Currently a skeleton (framed in P1-2); the concrete parse logic and modeling discipline are filled
> in P2 (aiifc consume-upstream parse chain — the large work item).**

## Planned files (P2)

| File | Content | Status |
|---|---|---|
| `bim_supplement_mapping.md` | bim_supplement.json (roof / special structures / PSETs) → IFC modeling mapping (IfcRoof / special elements / Psets) | 🔧 P2 |
| `building_zones_mapping.md` | building.json zones / storeys / spatial structure → IFC spatial hierarchy (IfcBuildingStorey / zones) | 🔧 P2 |
| `dxf_to_ifc_geometry.md` | per-zone DXF geometry (outline/core/walls/rooms/openings) → IFC geometry (walls/slabs/openings; XDATA key → element locating) | 🔧 P2 |

## Boundaries

- This directory holds **parse references only** (rules / mappings / discipline) — the parsing itself is
  performed by aiifc (the LLM) per CONSUME_UPSTREAM.md stage ②, guided by these rules.
- Upstream artifact schemas (bim_supplement / building.json) are owned by `skills/aiplan` /
  `skills/aidxf` — referenced here, not duplicated.
- The shared script-as-source contract (MUST #25-31) and script_lib live in `SKILL.md` +
  `references/docs/flows/`.
