# CONSUME_UPSTREAM.md —— cad->ifc consume-upstream path (bim_supplement + building.json + DXF → IFC script)

> This is the aiifc skill's **consume-upstream workflow** (cad->ifc pipeline): upstream aiplan produces
> `bim_supplement.json` (BIM supplement) + aidxf produces `building.json` (plan-form whole building,
> zones carry modelIds) + per-zone DXF platform models — aiifc **consumes these upstream artifacts**
> and deepens the already-bound IFC skeleton into a full IFC.
> Relationship to `PLAN_DXF_IFC.md`: PLAN_DXF_IFC is the **ifc-standalone path** (no upstream, design.json
> first); this file is the **cad->ifc consume-upstream path** (upstream exists, **no design.json** — the
> upstream already carries the complete design intent). Both share the **script-as-source main chain**
> (build script contract MUST #25-31 + sandbox build → IFC).
> **Path selection is dictated by the calling orchestrator (cad->ifc pipeline injects this path); this
> skill does not choose.**

## Positioning

- **Pipeline**: cad->ifc (`create_project(cad->ifc)` already initialized the IFC skeleton — bound up front).
- **No design.json**: the upstream (aiplan/aidxf) already produced the complete design intent
  (plan.json + building.json + DXF); aiifc does NOT re-frame design — it consumes the artifacts directly.
- **Deepen on the bound skeleton**: `create_project(cad->ifc)` already ran `init_model(ifc)` (modelId
  bound); this path deepens ON that skeleton (stage/run/save), not from scratch.

## Upstream artifacts (input anchors)

| Artifact | Source | Content | How to fetch |
|---|---|---|---|
| `bim_supplement.json` | aiplan (`deliver_plan`) | BIM supplement: roof / special structures / PSETs that CAD cannot cover | `get_project_plans` → plans/{projectID}/bim_supplement.json |
| `building.json` | aidxf (`deliver_building`) | plan-form whole building: site/standards/vertical_relations/design_rationale/requirements + zones[] (floors_from/to + **modelId** + typology/note/area) | `get_project_plans` → plans/{projectID}/building.json |
| per-zone DXF | aidxf (S4-b `init_model`) | per-zone platform model (modelId + build() script + DXF geometry: outline/core/walls/rooms/openings) | building.json `zones[].modelId` → `get_project_models` / `get_script` / `get_model_info` |

## Stage overview

```
① Read upstream   bim_supplement.json + building.json (get_project_plans)
                  + per-zone DXF platform models (zones[].modelId → get_project_models/get_script)
   │
   ▼
② Parse & consume bim_supplement (roof/special/PSET → IfcRoof/special elements/Psets)
                  + building.json (zones/storeys/spatial structure)
                  + DXF (outline/core/walls/rooms/openings → IFC geometry)
   │              [parse rules see references/consume_upstream/ — filled in P2]
   ▼
③ Produce build()  combine the three → build() script (script-as-source contract MUST #25-31:
   │               PARAMS + build(params,out_path) + deterministic_guid + validate)
   ▼
④ Deepen skeleton on the bound IFC skeleton: stage_script → run_script (sandbox verify) → save_script
   │               (v2/v3/... versioned)
   ▼
⑤ IFC deliver   versioned model (scripts/v{n}.py + versions/v{n}.ifc) + XKT derivative
```

## Per-stage MUSTs

### ① Read upstream
- First `get_project_plans` to read `bim_supplement.json` + `building.json` (missing → report to the
  calling agent; do NOT fabricate without upstream).
- `zones[].modelId` in building.json is the platform-model pointer of each zone's DXF — list via
  `get_project_models`, read via `get_script` / `get_model_info`.
- **Do NOT consume plan.json** (plan.json only feeds cad; ifc consumes bim_supplement + building.json + DXF).

### ② Parse & consume
- Parse bim_supplement.json (roof / special structures / PSETs) → corresponding IFC elements.
- Parse building.json zones/storeys/spatial structure → IFC spatial hierarchy (IfcBuildingStorey / zones).
- Parse per-zone DXF geometry (outline/core/walls/rooms/openings) → IFC geometry (walls/slabs/openings).
- [Parse rules / mapping tables in `references/consume_upstream/` — concrete logic & discipline in P2]

### ③ Produce build() script
- Combine the three into a **complete build() script** (script-as-source contract MUST #25-31):
  top-level PARAMS literal + build(params, out_path) + element GlobalIds via script_lib.deterministic_guid
  (stable unique keys) + validate exit.
- The script is the single source of truth (design JSON / DXF are auxiliary inputs — not versioned, not diffed).

### ④ Deepen skeleton
- Deepen on the bound skeleton: `stage_script` (build script) → `run_script` (sandbox verify buildable)
  → `save_script` (big version) — three-step, never rewrite wholesale (increment on the skeleton script).

### ⑤ IFC deliver
- Versioned model (scripts/v{n}.py + versions/v{n}.ifc) + XKT derivative (model page 3D).

## Split vs PLAN_DXF_IFC.md

| | CONSUME_UPSTREAM (cad->ifc) | PLAN_DXF_IFC (ifc standalone) |
|---|---|---|
| **Intake** | consume upstream (bim_supplement+building.json+DXF) | design.json draft (optional) |
| **design.json** | **not produced** (upstream carries intent) | produced (semantic draft for confirmation) |
| **Input** | bim_supplement + building.json + DXF modelIds | user requirement / idea |
| **Skeleton** | bound by create_project(cad->ifc), deepened on it | bound by create_project(ifc), deepened on it |
| **Shared** | script-as-source main chain (build script contract + sandbox build → IFC) | same |

> Resumption: building.json / bim_supplement are versioned in PlanStore (plans/{projectID}/); the IFC
> skeleton is registered via init_model — on interrupt, re-read upstream artifacts + skeleton script
> and continue deepening.
