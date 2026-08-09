# Modeling Workflows

## Mental Model

Principles in brief — each is expanded in its own section below (don't re-read here for detail).

- **Skeleton first, mandatory order** → [Pipeline Stages](#pipeline-stages): spatial tree before any element; Project→Spatial→Elements→Geometry→Openings→Data→Validate. Out-of-order = invalid IFC.
- **IfcRel\* is automatic** → [IfcRel\* Selection](#ifcrel-selection-discipline): the usecase creates the Rel (`assign_container`→Contained, `add_feature`→Voids...); never hand-write relationship entities.
- **Keyword arguments only** → [Calling Convention](#calling-convention): `run("pkg.uc", model, key=value)`.
- **Placement is relative; multi-storey passes world z** → [Placement Discipline](#placement-discipline).
- **Ground each step; validate in 3 layers** → [Grounding Discipline](#grounding-discipline): snapshot (during) → review (after) → validate (delivery).

## Calling Convention

```python
import ifcopenshell.api
model = ifcopenshell.api.run("project.create_file")
wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
```

All usecases follow `run("<package>.<usecase>", model, **kwargs)`.

## Pipeline Stages

```
Skeleton:  ① project.create_file
           ② root.create_entity(IfcProject)
           ③ unit.assign_unit
           ④ context.add_context(Model/Body/MODEL_VIEW)
           ⑤ root.create_entity(Site → Building → Storey)
           ⑥ aggregate.assign_object ×3

Elements:  ⑦ root.create_entity(IfcWall/IfcSlab/...)
           ⑧ geometry.edit_object_placement
           ⑨ geometry.add_*_representation + assign_representation
           ⑩ spatial.assign_container(→ Storey)

Openings:  ⑪ root.create_entity(IfcOpeningElement) + placement
           ⑫ feature.add_feature(opening → host wall)
           ⑬ root.create_entity(IfcDoor/IfcWindow) + placement
           ⑭ feature.add_filling(door → opening)

Data:      ⑮ type.assign_type + material.assign_material + color
           ⑯ pset.add_pset + edit_pset

Export:    ⑰ model.write + ifcopenshell.validate
```

Each step is pure-incremental. See `docs/flows/README.md` for runnable code per stage.

## Design JSON Framing (frame + parameterize, optional draft)

> For **complex floor plans** (multi-room partition runs), **irregular buildings** (sloped/curved walls), or **multi-storey**: the LLM MAY emit a **design JSON draft** (geometric intent, no coordinate math) instead of improvising coordinates in code — eliminating drift/misalignment/gaps. The draft is **auxiliary planning info**: not a complete representation, not versioned, not diffed. The deliverable and single source of truth is always the **build script** (script contract: SKILL.md MUST #25-31).

### When to use

- Complex / irregular / multi-storey → design JSON draft framing, then script
- Simple single wall/slab → direct code (Pipeline Stages above)

### Three-layer method

```
① Frame:     LLM emits design JSON draft (whole frame + per-floor geometry intent)
② Normalize: flows/design_builder.py → features.json
             (modulus snap + closure + axis-grid alignment + typical-floor expansion)
③ Build:     per-building script (template flows/build_script_template.py)
             reads features.json and walks the Pipeline with flows single-step ops → IFC
             → the resulting script becomes the source of truth; the draft is discarded
```

### Principles

- **LLM never computes coordinates**: only geometric intent (axis / outline / along-axis / axis-grid path)
- **Modulus constraint**: builder snaps to `meta.modulus` (default 0.1m), removing drift
- **Geometry only, not construction**: the JSON says where/how big; how to build is decided downstream from `docs/design/` recipes — design space stays downstream, not in JSON fields
- **Design before JSON**: choose massing/roof/stairs/windows from `DESIGN_PATTERNS.md` + `docs/design/` first; a design JSON expresses a *chosen* design, not an arbitrary fixed layout
- **Schema contract**: see `DESIGN_JSON_SCHEMA.md` (field definitions + wall forms + examples)
- **Script is the source of truth**: once the build script exists, all later changes go to the script (PARAMS / incremental edits) — never back to the JSON draft

### Wall forms (pick per floor plan)

| form | field | use for |
|---|---|---|
| axis straight | `axis:[[x1,y1],[x2,y2]]` | exterior / single interior (can hold openings) |
| axis polyline | `axis` multi-point | sloped / zigzag walls |
| axis-grid path | `path:[{x,y},...]` | partition runs (orthogonal, no coords) |
| arc | `arc:{center,r,a0,a1}` | curved walls (chord-approximated) |

Stairs / roof / balcony / parapet: **mark position/class only** (`at`+`shaft` / `type`); the build script constructs them from `docs/design/` recipes.

## IfcRel\* Selection Discipline

Never create IfcRel\* manually. The correct usecase creates the correct Rel automatically:

| Operation | Usecase | Auto-created Rel |
|---|---|---|
| Spatial tree | `aggregate.assign_object` | IfcRelAggregates |
| Element → Storey | `spatial.assign_container` | IfcRelContainedInSpatialStructure |
| Type → Element | `type.assign_type` | IfcRelDefinesByType |
| Cut opening | `feature.add_feature` | IfcRelVoidsElement |
| Fill opening | `feature.add_filling` | IfcRelFillsElement |
| Attach pset | `pset.add_pset` | IfcRelDefinesByProperties |
| Assign material | `material.assign_material` | IfcRelAssociatesMaterial |

## Placement Discipline

Right-hand coordinates: X=East, Y=North, Z=Up. Matrix is 4×4 (rotation + translation):

```python
import numpy as np
matrix = np.eye(4)
matrix[0][3] = 2.0  # X offset (metres with is_si=True)
matrix[1][3] = 3.0  # Y
ifcopenshell.api.run("geometry.edit_object_placement", model,
    product=wall, matrix=matrix, is_si=True)
```

- Element placement is **relative to its container**, not world coordinates.
- Storey placement carries the elevation; element placement carries the in-storey position.
- `is_si=True`: metres. Omitted: project units (mm).

### Multi-Storey: Always Use World Coordinates (verified, ifcopenshell 0.8.x)

`create_2pt_wall`'s `elevation` and `edit_object_placement`'s `matrix` both interpret values as **world coordinates**; the usecase writes compensating relative placements against the container (Storey) chain. Therefore **never** pass storey-local coordinates on multi-storey buildings:

| Element | Correct (world) | Wrong (local) |
|---|---|---|
| Storey-2 wall | `create_2pt_wall(elevation=3.3)` | `elevation=0` → overlaps ground floor |
| Storey-2 floor slab | `edit_object_placement(z=3.3)` | `z=0` → falls to ground |
| Flat roof (2 × 3.3m) | `z=6.6` | `z=3.3` → sits on floor-2 ceiling |

After placement, spot-check `world_xyz_mm` via `tracker.snapshot()`: each storey's walls should report `z ∈ {0, 3300, ...}`.

### Multi-Axis Placement

Tilted members (sunshade / ramp) chain rotation matrices `M = T @ Ry(tilt) @ Rz(phi)` — see `docs/flows/placement_tricks.md`.

## Property Set Discipline

- Verify applicability before attaching: `PsetQto.get_applicable_names(class)` → see `docs/psets/README.md`.
- Property names must match schema exactly: `doc.get_property_set_doc(pset)`.
- Pset = designer-specified (FireRating, IsExternal); Qto = geometry-derived (NetVolume, Length).
- Real files use a **subset** of schema properties — not all Pset fields are required.

## Grounding Discipline (three-layer validation)

- **During** — `tracker.snapshot()` after each major step (incremental, fail-fast): read `world_xyz_mm`, check `fills_opening` / `voids_wall` links. See `docs/flows/tracker.py`.
- **After** — `design_review.run(model, building_type=...)` for geometric integrity (GI) + design quality (PR/RH/MC/CP/SQ). See `docs/flows/design_review.py` and `SPATIAL_QUALITY.md`.
- **Before delivery** — `ifcopenshell.validate` for schema legality (export gate).

For quick facts, print concisely (`len(model.by_type("IfcWall"))`, `wall.GlobalId`) — never dump whole model objects.

## Openings & Inspecting

- **Opening discipline**: world coordinates before `feature.add_feature` (auto wall-relative) + thickness ≥ 1.5× wall + never hand-set wall-local. Details: `docs/flows/placement_tricks.md` + `docs/flows/pitfalls.md` (O1/O2).
- **ifc_inspect** (on-demand, not every build): triggers = design_review flags errors / user adjustment / externally-modified IFC. Usage + token discipline: `docs/flows/README.md` → Tools.

## Type Library

- Create **types before instances** (`IfcWallType` before `IfcWall`); assign with `type.assign_type`.
- Prefer **parameterized profiles** (`IfcIShapeProfileDef`, `IfcRectangleProfileDef`) over arbitrary profiles.
- Type names follow conventions (e.g., "EXT-200" for 200mm exterior wall).

## Modifying an Existing Model

When the user asks to change an existing model, follow this decision tree — **never improvise against the IFC blindly**. Work on a staging copy, self-check, then atomically replace the target file.

**Step 0 — Decide the path: parametric vs surgical**
- **Parametric path (preferred)**: if the model was generated by a build script (e.g. `model.py` in the working directory), **the script is the single source of truth — changing the model = changing the script**. Edit incrementally (SKILL.md MUST #28): tunable values go through the script's `PARAMS` dict; geometric/logic changes are minimal targeted edits. NEVER rewrite or regenerate the script from scratch. Re-run it into a staging copy, self-check, then atomically replace. The edited script (and its readable diff) becomes the provenance of the next version.
- **Surgical path**: if no build script exists, edit the IFC in place with ifcopenshell (staging copy → modify → self-check → atomic replace). Deliverable has no script; the change is a one-off.

**Step 1 — Inspect before you touch (mandatory on the surgical path, recommended on both):**
```bash
<your-python> <skill_root>/references/docs/flows/ifc_inspect.py model.ifc --no-psets        # 摸底：结构树+构件清单
<your-python> <skill_root>/references/docs/flows/ifc_inspect.py model.ifc --storey "Level 2" --class IfcWall   # 定向深挖受影响区域
```
- Use it to read **real coordinates/placements/psets** of the region you will change — never guess geometry from the request text.
- Token discipline unchanged: `--no-psets` first, then `--storey` / `--class` / `--ids` to dig. Output lands in `analysis_results/<model>_structure.json`.
- On the parametric path, inspect the **staging copy** after re-running to verify the change landed; on the surgical path, inspect before (plan) and after (verify).

## Navigation

**In `docs/flows/`** (runnable code + accumulative docs) — full index at `docs/flows/README.md`:
- Script contract: `script_lib.py` (deterministic_guid / attach_design_key / create_skeleton / write_and_validate / validate_script_contract)
- Framing: `design_builder.py`, `build_script_template.py`
- Single-step ops: `skeleton / wall / slab_profile / opening_door / type_material / pset_qto.py`, `full_building.py`
- Performance / quality / tools: `performance.py`, `style_color.py`, `tracker.py`, `design_review.py`, `ifc_inspect.py`
- Accumulative docs: `pitfalls.md`, `placement_tricks.md`

**Companion references**:
- `DESIGN_JSON_SCHEMA.md` — design JSON contract (field definitions)
- `DESIGN_PATTERNS.md` — concept design + component-building index
- `docs/design/README.md` — component-building recipes (roof/stairs/windows/parapet/balcony)
- `docs/entities/README.md` — entity attribute specs
- `docs/psets/README.md` — applicable Pset/Qto index
- `SPATIAL_QUALITY.md` — design review rules
