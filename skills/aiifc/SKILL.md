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
- Python runtime: needs `ifcopenshell` + `ifcquery` + `numpy` (see `requirements.txt`; PyPI releases, no local source). Use whichever Python has them installed — system `python3` often lacks ifcopenshell.

## MUST Requirements

**Reading:**
1. Read `references/SDK_OVERVIEW.md` and `references/docs/api/README.md` before choosing usecases.
2. Read the exact usecase Markdown page (`docs/api/<pkg>.<usecase>.md`) for every usecase you call.
3. Read `references/MODELING_WORKFLOWS.md` before building your first model.
4. **Read `references/SPATIAL_QUALITY.md` BEFORE framing any design JSON** — footprint articulation (CP-05), door swing clearance (GI-08), stair continuity (GI-09) must be internalized up front so the design JSON is born compliant. Also read `references/DESIGN_PATTERNS.md` before choosing massing/facade/spatial organization.
5. **Component recipes — consult before building any element**: check `references/docs/design/` for a matching recipe. The index is in `docs/design/README.md`.

> **Optional workflow**: when a task benefits from staged planning (assist a designer from idea to IFC), consult `workflows/PLAN_DXF_IFC.md` — plan → DXF → IFC. It is a **selective feature, not mandatory**; skip it entirely for simple direct builds (`simple wall/slab` MUST #19) or when the user's input already targets a specific stage.

**API usage:**
6. All API calls use **keyword arguments**; the first positional argument is always `model`.
7. Use `ifcopenshell.api.run("<package>.<usecase>", model, **kwargs)`.
8. Follow the documented API signatures exactly — do not invent parameters.

**Skeleton:**
9. **Skeleton first**: build Project→Site→Building→Storey spatial tree before any element or geometry.
10. **Every element needs a container**: always `spatial.assign_container`. No orphan elements.

**Geometry:**
11. **If a product has geometry, it needs placement**: `geometry.edit_object_placement` for every product with a body representation.
12. **`create_2pt_wall` returns the representation but does NOT assign it** — always `geometry.assign_representation` separately.

**Opening:**
13. **Set world coordinates for openings before `feature.add_feature`** (it converts world → relative automatically). Never set "wall-local" coordinates manually.
14. **Opening thickness must exceed wall thickness** (≥ 1.5×) to fully penetrate.

**Normativity:**
15. **Pset applicability**: before `pset.add_pset`, verify via `PsetQto.get_applicable_names()` (see PSET_REFERENCE.md).
16. **PredefinedType enum**: verify the value is in the entity's allowed enum list (see ENTITY_SPECS.md).
17. **Pset + material coverage**: every product class must get ≥1 pset AND ≥1 material; spot-check with `util.element.get_psets(e)` / `get_material(e)`.

**Generation (design JSON first for complex geometry):**
18. **Complex buildings**: **frame the geometry with a design JSON first** — LLM outputs parametric intent, never coordinate math. See `references/DESIGN_JSON_SCHEMA.md` for the contract. Then `flows/design_builder.py` → `features.json` → per-building build script.
19. **Simple single wall/slab**: may still be coded directly (Pipeline Stages).

**Validation (three layers):**
20. **During**: `tracker.snapshot()` after each step changing geometry or placement.
21. **After**: run `flows/design_review.py` once per build as a **fixed black-box check** — read its text report. If errors, fix the model against `references/SPATIAL_QUALITY.md`.
22. **Export**: `model.write()` is followed by `ifcopenshell.validate`. No model is complete without passing schema validation.

**Output:**
23. **Output paths (generic)**: generated IFC → working directory as **`model.ifc`** (write via staging copy, self-check, then atomic replace). If your host provides a specific output contract, follow that instead.
24. **No visualization rendering**: do NOT call `ifc_plot` / `ifc_render` / any image output. All verification is **text-only**: `ifcopenshell.validate` + `design_review.py` + `ifc_inspect.py`.

## Entity Mental Model

Every element needs four components:

| Component | Usecase | What it does |
|---|---|---|
| **Entity** | `root.create_entity` | Creates the IFC entity |
| **Placement** | `geometry.edit_object_placement` | Position/rotation |
| **Representation** | `geometry.add_*_representation` + `assign_representation` | Body geometry |
| **Container** | `spatial.assign_container` | Places into a storey |

Optional: **Type** (`type.assign_type`), **Material** (`material.assign_material`), **Style/color** (`style_color.py`), **Pset/Qto** (`pset.add_pset`/`add_qto`), **Opening** (`feature.add_feature`), **Filling** (`feature.add_filling`).

## References (Reading Map)

| Doc | Role |
|---|---|
| `references/SDK_OVERVIEW.md` | Package map, entity-relationship model, typical patterns |
| `references/MODELING_WORKFLOWS.md` | Pipeline stages, placement/opening/grounding discipline, **Design JSON 框定**, ifc_inspect |
| `references/DESIGN_JSON_SCHEMA.md` | Design JSON format contract (wall forms, normalization rules, full example) |
| `references/DESIGN_PATTERNS.md` | Design patterns: massing, facade, structure, circulation, spatial |
| `references/ENTITY_SPECS.md` | Entity attribute tables (REQ/OPT/type/source) |
| `references/PSET_REFERENCE.md` | Applicable Pset/Qto per element type |
| `references/SPATIAL_QUALITY.md` | Design review rules (SS/GI/PR/RH/MC/CP/FD/SQ) |
| `references/docs/api/README.md` + `<pkg>.<usecase>.md` | API index (14 categories, 103 usecases) + exact signatures |
| `references/docs/flows/README.md` + `*.py` | Runnable per-stage code and tools (tracker / design_review / ifc_inspect / **dxf_from_design**) |
| `references/docs/design/README.md` + recipes | Component building recipes (stairs, roof, windows, parapet, balcony) |
| `templates/build_skeleton.py` | Minimal complete model (skeleton + wall + slab) — copy and edit |
| `workflows/PLAN_DXF_IFC.md` | **工作流编排**：plan → DXF → IFC 三阶段顺序与跳步规则（辅助设计师） |

## Installing the skill

This skill is an agent-agnostic directory bundle (SKILL.md + references/). Any tool supporting the Anthropic Agent Skills layout can load it:

**opencode:**
```bash
# Project-level: add to opencode.json
# "skills": { "paths": ["skills"] }
# (aiifc is already under skills/aiifc in this repo)

# Or global (symlink or copy):
ln -s $(pwd)/skills/aiifc ~/.config/opencode/skills/aiifc
```

**Claude Code:**
```bash
# Copy or symlink to the Claude skills directory:
ln -s $(pwd)/skills/aiifc ~/.claude/skills/aiifc
```

**Cursor / other Agent Skills tools:**
```bash
# Copy the skill directory to the agent's skills path:
cp -r skills/aiifc <agent-skills-dir>/aiifc
```

**Distributable bundle:**
```bash
python tools/skill_pack_aiifc.py --archive   # produces skills/dist/aiifc.tar.gz
tar xzf skills/dist/aiifc.tar.gz -C ~/.config/opencode/skills/
```

## Demo integration (AI_IFC viewer — optional, not part of the distributable skill)

When this skill runs **inside the AI_IFC demo** (opencode serve + viewer), the host provides a fixed contract that overrides the generic output paths (MUST #23). This section is maintained in-repo for the demo and is **not** part of the distributable skill bundle.

- Build scripts (`.py`) → `examples/`; generated IFC files → **`viewer/data/uploads/{modelId}.ifc`** (write via a staging copy, self-check, then atomic replace; `modelId` is injected via system context).
- **design.json** (complex-build artifact, MUST #18) → `viewer/data/staging/{modelId}.design.json`; the system archives it per version to `models/{id}/designs/v{n}.json` alongside the build script.
- Python runtime: **always `.venv/bin/python`** in the demo workspace (ifcopenshell / ifcquery / numpy preinstalled per `requirements.txt`).
- Agent rules live in `.opencode/agent/ifc-demo.md` (write scoping, staging, atomic-replace, no viewer HTTP calls); the Go server auto-handles commit/version/XKT-reconvert on `file.edited` + `session.idle`.