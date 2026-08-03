---
name: aiifc
description: Thin IfcOpenShell reference skill for IFC model authoring via ifcopenshell.api, including spatial structure, geometry, openings, materials, psets and design-review workflows.
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
- Python runtime: the skill's flows/tools need `ifcopenshell` + `ifcquery` + `numpy` (see `requirements.txt` at skill root; PyPI 发布版, no local source dependency). Use whichever Python has them installed — system `python3` often lacks ifcopenshell. (When running inside the AI_IFC demo, use `.venv/bin/python` as detailed in the Demo integration section below.)

## MUST Requirements

**Reading:**
1. Read `references/SDK_OVERVIEW.md` and `references/docs/api/README.md` before choosing usecases.
2. Read the exact usecase Markdown page (`docs/api/<pkg>.<usecase>.md`) for every usecase you call.
3. Read `references/MODELING_WORKFLOWS.md` before building your first model.
4. **Read `references/SPATIAL_QUALITY.md` BEFORE framing any design JSON** — it is a design constraint (not only a post-check): footprint articulation (CP-05, no lazy rectangles), door swing clearance (GI-08), stair continuity (GI-09) must be internalized up front so the design JSON is born compliant. Also read `references/DESIGN_PATTERNS.md` before choosing massing/facade/spatial organization.
5. **Component recipes — consult before building any element**: Before constructing a specific component (window, door, stair, roof, parapet, balcony, atrium, massing variant, etc.), check the component-recipe library under `references/docs/design/` for a matching recipe. Each recipe specifies the IFC class, geometry method, parameter range, and variants — follow its parametric scheme rather than inventing coordinates/parameters/types; fall back to the generic API only when no recipe matches. This is a per-component, high-frequency habit, independent of the complex design-JSON flow (#18). The index of which recipe covers which component lives in `docs/design/README.md` — read it to locate the right recipe. 

**API usage:**
6. All API calls use **keyword arguments**; the first positional argument is always `model`.
7. Use `ifcopenshell.api.run("<package>.<usecase>", model, **kwargs)` as the calling convention.
8. Follow the documented API signatures exactly — do not invent parameters.

**Skeleton:**
9. **Skeleton first**: build Project→Site→Building→Storey spatial tree before any element or geometry.
10. **Every element needs a container**: always `spatial.assign_container`. No orphan elements.

**Geometry:**
11. **If a product has geometry, it needs placement**: `geometry.edit_object_placement` for every product with a body representation.
12. **`create_2pt_wall` returns the representation but does NOT assign it** — always `geometry.assign_representation` separately.

**Opening:**
13. **Set world coordinates for openings before `feature.add_feature`** (it converts world → relative automatically). Never set "wall-local" coordinates manually — double-offset error.
14. **Opening thickness must exceed wall thickness** (≥ 1.5×) to fully penetrate.

**Normativity:**
15. **Pset applicability**: before `pset.add_pset`, verify via `PsetQto.get_applicable_names()` (see PSET_REFERENCE.md).
16. **PredefinedType enum**: verify the value is in the entity's allowed enum list (see ENTITY_SPECS.md).
17. **Pset + material coverage**: every product class must get ≥1 pset AND ≥1 material; spot-check with `util.element.get_psets(e)` / `get_material(e)`.

**Generation (design JSON first for complex geometry):**
18. **Complex buildings** (multi-room floor plans, irregular/sloped/curved walls, multi-storey): **frame the geometry with a design JSON first** — the LLM outputs parametric intent (footprint / axis paths / openings along-axis / stairs / roof), never coordinate math. **But a design JSON is a design decision, not a fixed layout to follow blindly**: before emitting it, consult `DESIGN_PATTERNS.md` (massing/facade/structure/circulation/spatial) and `docs/design/` (roof/stairs/windows/parapet/balcony recipes) to *choose* the design; and the downstream build script must consult `docs/api/` usecases + `docs/design/` recipes for component details rather than following the JSON literally. Then `flows/design_builder.py` → `features.json` → per-building build script. **Do NOT improvise coordinates for complex geometry** — that is the root cause of drift / misalignment / gaps.
19. **Simple single wall/slab**: may still be coded directly (Pipeline Stages).

**Validation (three layers, see MODELING_WORKFLOWS → Grounding):**
20. **During**: `tracker.snapshot()` after each step that changes geometry or placement. Curtain-wall doors/windows are exempt from opening-link checks (they sit in the grid, not in `IfcOpeningElement`).
21. **After**: run `flows/design_review.py` once per build as a **fixed black-box check** — just run it and read its text report (`ERRORS / WARNINGS / INFO`). **Do NOT spend effort understanding or editing its code.** If it flags errors, fix the MODEL against the rule descriptions in `references/SPATIAL_QUALITY.md` — that file is the single source of truth for what each rule means (read it, not the tool's implementation). These are the same rules you internalized BEFORE generating (MUST #4), so a compliant design JSON should pass without a fix-loop. Never write your own verification script to replace it.
22. **Export**: `model.write()` is followed by `ifcopenshell.validate`. No model is complete without passing schema validation.

**Output & Verification:**
23. **Output paths (generic)**: build scripts (`.py`) → working directory as `model.py`; generated IFC → working directory as **`model.ifc`** (write via a staging copy, self-check, then atomic replace). If your host provides a specific output contract (see the **Demo integration** section below when running inside the AI_IFC viewer), follow that instead. design_review/ifc_inspect analysis JSONs are auto-written by the tools to `analysis_results/` (working directory, default tool behavior, no action needed).
24. **No visualization rendering**: do NOT call `ifc_plot` / `ifc_render` / any PNG/SVG/image output. The agent cannot read images, and the user inspects the IFC in their own BIM viewer. All verification is **text-only**: `ifcopenshell.validate` (schema legality) + `design_review.py` (quality report) + `ifc_inspect.py` (on-demand filtered text dump).

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

## Modifying an Existing Model

When the user asks to change an existing model, follow this decision tree — **never improvise against the IFC blindly**. Work on a staging copy, self-check, then atomically replace the target file.

**Step 0 — Decide the path: parametric vs surgical**
- **Parametric path (preferred)**: if the model was generated by a build script (e.g. `model.py` in the working directory), edit the script's parameters/geometry logic, re-run it to regenerate the whole model into a staging copy, self-check, then atomically replace. This keeps the model reproducible — the edited script becomes the provenance of the next version.
- **Surgical path**: if no build script exists, edit the IFC in place with ifcopenshell (staging copy → modify → self-check → atomic replace). Deliverable has no script; the change is a one-off.

**Step 1 — Inspect before you touch (mandatory on the surgical path, recommended on both):**
```bash
<your-python> <skill_root>/references/docs/flows/ifc_inspect.py model.ifc --no-psets        # 摸底：结构树+构件清单
<your-python> <skill_root>/references/docs/flows/ifc_inspect.py model.ifc --storey "Level 2" --class IfcWall   # 定向深挖受影响区域
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

## Demo integration (AI_IFC viewer — optional, not part of the distributable skill)

When this skill runs **inside the AI_IFC demo** (opencode serve + viewer), the host provides a fixed contract that overrides the generic output paths (MUST #23). This section is maintained in-repo for the demo and is **not** part of the distributable skill bundle.

- Build scripts (`.py`) → `examples/`; generated IFC files → **`viewer/data/uploads/{modelId}.ifc`** (write via a staging copy, self-check, then atomic replace; `modelId` is injected via system context).
- **design.json** (complex-build artifact, MUST #18) → `viewer/data/staging/{modelId}.design.json`; the system archives it per version to `models/{id}/designs/v{n}.json` alongside the build script.
- Python runtime: **always `.venv/bin/python`** in the demo workspace (ifcopenshell / ifcquery / numpy preinstalled per `requirements.txt`).
- Agent rules live in `.opencode/agent/ifc-demo.md` (write scoping, staging, atomic-replace, no viewer HTTP calls); the Go server auto-handles commit/version/XKT-reconvert on `file.edited` + `session.idle`.
