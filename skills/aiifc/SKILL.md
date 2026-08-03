---
name: aiifc
description: Thin IfcOpenShell reference skill for IFC model authoring via ifcopenshell.api.make you a expert in ifc archetecture and modeling workflows.
license: LGPL-3.0
compatibility: Documentation/reference bundle for ifcopenshell API surfaces.
metadata:
  project: aiifc
  package-name: ifcopenshell
---

# AI_IFC SDK Skill

## Philosophy

- Thin reference skill: docs only, no SDK source code bundled.
- Agent reads these docs, then writes ifcopenshell.api code directly (not MCP tool calls).
- Python runtime (demo environment): **always use `.venv/bin/python`** (ifcopenshell 0.8.5 preinstalled); system `python3` has NO ifcopenshell.

## MUST Requirements

**Reading:**
1. Read `references/SDK_OVERVIEW.md` and `references/docs/api/README.md` before choosing usecases.
2. Read the exact usecase Markdown page (`docs/api/<pkg>.<usecase>.md`) for every usecase you call.
3. Read `references/MODELING_WORKFLOWS.md` before building your first model.
4. **Read `references/SPATIAL_QUALITY.md` BEFORE framing any design JSON** — it is a design constraint (not only a post-check): footprint articulation (CP-05, no lazy rectangles), door swing clearance (GI-08), stair continuity (GI-09) must be internalized up front so the design JSON is born compliant. Also read `references/DESIGN_PATTERNS.md` before choosing massing/facade/spatial organization.
5. **Component recipes — consult before building any element**: Before constructing a specific component (window, door, stair, roof, parapet, balcony, atrium, massing variant, etc.), check the component-recipe library under `references/docs/design/` for a matching recipe. Each recipe specifies the IFC class, geometry method, parameter range, and variants — follow its parametric scheme rather than inventing coordinates/parameters/types; fall back to the generic API only when no recipe matches. This is a per-component, high-frequency habit, independent of the complex design-JSON flow (#20). The index of which recipe covers which component lives in `docs/design/README.md` — read it to locate the right recipe. 

**API usage:**
5. All API calls use **keyword arguments**; the first positional argument is always `model`.
6. Use `ifcopenshell.api.run("<package>.<usecase>", model, **kwargs)` as the calling convention.
7. Follow the documented API signatures exactly — do not invent parameters.

**Skeleton:**
8. **Skeleton first**: build Project→Site→Building→Storey spatial tree before any element or geometry.
9. **Every element needs a container**: always `spatial.assign_container`. No orphan elements.

**Geometry:**
10. **If a product has geometry, it needs placement**: `geometry.edit_object_placement` for every product with a body representation.
11. **`create_2pt_wall` returns the representation but does NOT assign it** — always `geometry.assign_representation` separately.

**Opening:**
12. **Set world coordinates for openings before `feature.add_feature`** (it converts world → relative automatically). Never set "wall-local" coordinates manually — double-offset error.
13. **Opening thickness must exceed wall thickness** (≥ 1.5×) to fully penetrate.

**Normativity:**
17. **Pset applicability**: before `pset.add_pset`, verify via `PsetQto.get_applicable_names()` (see PSET_REFERENCE.md).
18. **PredefinedType enum**: verify the value is in the entity's allowed enum list (see ENTITY_SPECS.md).
19. **Pset + material coverage**: every product class must get ≥1 pset AND ≥1 material; spot-check with `util.element.get_psets(e)` / `get_material(e)`.

**Generation (design JSON first for complex geometry):**
20. **Complex buildings** (multi-room floor plans, irregular/sloped/curved walls, multi-storey): **frame the geometry with a design JSON first** — the LLM outputs parametric intent (footprint / axis paths / openings along-axis / stairs / roof), never coordinate math. **But a design JSON is a design decision, not a fixed layout to follow blindly**: before emitting it, consult `DESIGN_PATTERNS.md` (massing/facade/structure/circulation/spatial) and `docs/design/` (roof/stairs/windows/parapet/balcony recipes) to *choose* the design; and the downstream build script must consult `docs/api/` usecases + `docs/design/` recipes for component details rather than following the JSON literally. Then `flows/design_builder.py` → `features.json` → per-building build script. **Do NOT improvise coordinates for complex geometry** — that is the root cause of drift / misalignment / gaps.
21. **Simple single wall/slab**: may still be coded directly (Pipeline Stages).

**Validation (three layers, see MODELING_WORKFLOWS → Grounding):**
14. **During**: `tracker.snapshot()` after each step that changes geometry or placement. Curtain-wall doors/windows are exempt from opening-link checks (they sit in the grid, not in `IfcOpeningElement`).
15. **After**: run `flows/design_review.py` once per build as a **fixed black-box check** — just run it and read its text report (`ERRORS / WARNINGS / INFO`). **Do NOT spend effort understanding or editing its code.** If it flags errors, fix the MODEL against the rule descriptions in `references/SPATIAL_QUALITY.md` — that file is the single source of truth for what each rule means (read it, not the tool's implementation). These are the same rules you internalized BEFORE generating (MUST #4), so a compliant design JSON should pass without a fix-loop. Never write your own verification script to replace it.
16. **Export**: `model.write()` is followed by `ifcopenshell.validate`. No model is complete without passing schema validation.

**Output & Verification:**
22. **Output paths (mandatory, demo adaptation)**: build scripts (`.py`) → `examples/`; generated IFC files → **`viewer/data/uploads/{modelId}.ifc`** (write via a staging copy, self-check, then atomic replace; modelId is given via system context — never the repo root or `examples/` root); **design.json (complex-build artifact, MUST #20) → `viewer/data/staging/{modelId}.design.json`** (the system archives it per version to `models/{id}/designs/v{n}.json`, kept in sync with the build script); design_review/ifc_inspect analysis JSONs are auto-written by the tools to `analysis_results/` (project root, default tool behavior, no action needed).
23. **No visualization rendering**: do NOT call `ifc_plot` / `ifc_render` / any PNG/SVG/image output. The agent cannot read images, and the user inspects the IFC in their own BIM viewer. All verification is **text-only**: `ifcopenshell.validate` (schema legality) + `design_review.py` (quality report) + `ifc_inspect.py` (on-demand filtered text dump).

## Type Library

- Create **types before instances** (`IfcWallType` before `IfcWall`); assign with `type.assign_type`.
- Prefer **parameterized profiles** (`IfcIShapeProfileDef`, `IfcRectangleProfileDef`) over arbitrary profiles.
- Type names follow conventions (e.g., "EXT-200" for 200mm exterior wall).

## Modeling Mental Model

- **Skeleton first, pure incremental**: spatial tree built once, never modified; each step only adds.
- **IfcRel\* is automatic**: `spatial.assign_container` → `IfcRelContainedInSpatialStructure`; `feature.add_feature` → `IfcRelVoidsElement`. Never hand-write relationship entities.
- **World coordinates for placement (ifcopenshell 0.8.x)**: `create_2pt_wall(elevation=...)` and `edit_object_placement(matrix=...)` accept world coordinates and compensate internally. Multi-storey models always pass world z — never storey-local z.
- **Pipeline order is mandatory**: Project → Spatial → Elements → Geometry → Openings → Data → Validate.
- **Frame + parameterize for complex geometry**: design JSON (intent) → `design_builder` → features.json (framed geometry) → build script (Pipeline) → IFC. Three layers: intent → framed geometry → build. See MODELING_WORKFLOWS → Design JSON 框定.

## Entity Mental Model

Every element has a lifecycle with four required components — missing any one produces invisible or broken output:

| Component | Usecase | What it does |
|---|---|---|
| **Entity** | `root.create_entity` | Creates the IFC entity |
| **Placement** | `geometry.edit_object_placement` | Position/rotation |
| **Representation** | `geometry.add_*_representation` + `assign_representation` | Body geometry |
| **Container** | `spatial.assign_container` | Places into a storey |

Optional, attach after the four: **Type** (`type.assign_type`), **Material** (`material.assign_material`), **Style/color** (dual-layer: `style.assign_material_style` + `style.assign_representation_styles` direct on Body — required for multi-layer materials, see `flows/style_color.py`), **Pset/Qto** (`pset.add_pset`/`add_qto`), **Opening** (`feature.add_feature`), **Filling** (`feature.add_filling`).

## Inspecting Models (ifc_inspect)

`flows/ifc_inspect.py` is the on-demand geometry inspector — never run on every build. Triggers:

1. **design_review reports errors**: the analysis JSON already embeds `error_elements` (placement/geometry/container/nearest_wall for every flagged element, hardcoded). Call ifc_inspect only when you need *more* than that.
2. **User requests a model adjustment**: scan the affected region to see current state before editing.
3. **User returns an externally-modified IFC**: scan to learn what changed, then follow up in Python.

Recon lean (`--no-psets`), then go targeted (`--storey` / `--class` / `--ids`). See MODELING_WORKFLOWS → Inspecting Models.

## Modifying an Existing Model (demo workflow)

In the demo, every project model carries its **build provenance**: `viewer/data/models/{modelId}/scripts/v{n}.py` is the exact script that produced version `v{n}` (absent versions were direct IFC edits). When the user asks to change an existing model, follow this decision tree — **never improvise against the IFC blindly**.

**Step 0 — Locate the current build script (能力一):**
```bash
ls viewer/data/models/{modelId}/scripts/          # 按 v{n} 数字取最大者即当前脚本
```
- **Script exists → parametric path (preferred)**: copy the latest `v{n}.py` to `viewer/data/staging/`, edit its parameters/geometry logic per the request, re-run it (with `.venv/bin/python`) to regenerate the whole model into a staging copy, self-check, then atomically replace `uploads/{modelId}.ifc` (per agent rules). This keeps the model reproducible — your edited script becomes the provenance of the next version.
- **No script → surgical path**: edit the IFC in place with ifcopenshell (staging copy → modify → self-check → atomic replace). Deliverable has no script; the version is marked as a direct edit.

**Step 1 — Inspect before you touch (能力二, mandatory on the surgical path, recommended on both):**
```bash
.venv/bin/python skills/aiifc/references/docs/flows/ifc_inspect.py viewer/data/uploads/{modelId}.ifc --no-psets        # 摸底：结构树+构件清单
.venv/bin/python skills/aiifc/references/docs/flows/ifc_inspect.py viewer/data/uploads/{modelId}.ifc --storey "Level 2" --class IfcWall   # 定向深挖受影响区域
```
- Use it to read **real coordinates/placements/psets** of the region you will change — never guess geometry from the request text.
- Token discipline unchanged: `--no-psets` first, then `--storey` / `--class` / `--ids` to dig. Output lands in `analysis_results/<model>_structure.json`.
- On the parametric path, inspect the **staging copy** after re-running to verify the change landed; on the surgical path, inspect before (plan) and after (verify).

## Example SDK Usage

Minimal complete model (skeleton + one wall + one slab):

```python
import numpy as np
import ifcopenshell
import ifcopenshell.api

# Skeleton
model = ifcopenshell.api.run("project.create_file")
project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
ifcopenshell.api.run("unit.assign_unit", model)
model3d = ifcopenshell.api.run("context.add_context", model, context_type="Model")
body = ifcopenshell.api.run("context.add_context", model, context_type="Model",
    context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)
site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite")
building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding")
storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey")
storey.Elevation = 0.0  # SS-03: every storey must have Elevation
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])

# Wall (entity → placement → representation → container)
wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall)
rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
    context=body, length=5, height=3, thickness=0.2)
ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=rep)
ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])

# Export + validate
model.write("model.ifc")
import ifcopenshell.validate
logger = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate("model.ifc", logger)
assert not logger.statements, f"Validation failed: {logger.statements}"
```
## References (Reading Map)

| Doc | Role |
|---|---|
| `references/SDK_OVERVIEW.md` | Package map, entity-relationship model, typical patterns |
| `references/MODELING_WORKFLOWS.md` | Pipeline stages, placement/opening/grounding discipline, **Design JSON 框定**(复杂户型/异形精确生成), ifc_inspect follow-up |
| `references/DESIGN_JSON_SCHEMA.md` | **Design JSON 格式契约**(LLM 框定意图的字段定义 / 4 种墙 / 规范化规则 / 完整示例) |
| `references/ENTITY_SPECS.md` | Entity attribute tables (REQ/OPT/type/source) |
| `references/PSET_REFERENCE.md` | Applicable Pset/Qto per element type |
| `references/DESIGN_PATTERNS.md` | Design patterns: massing, facade, structure, circulation, spatial |
| `references/SPATIAL_QUALITY.md` | Design review rules (SS/GI/PR/RH/MC/CP/FD/SQ) |
| `references/docs/api/README.md` + `<pkg>.<usecase>.md` | API index (14 categories, 103 usecases) + exact signatures |
| `references/docs/flows/*.py` | Runnable per-stage code + tools (tracker / design_review / ifc_inspect) |
