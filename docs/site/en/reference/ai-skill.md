# AI Skill (aiifc)

An **IfcOpenShell authoring skill** for AI agents — letting an agent write `ifcopenshell.api` code directly to create or modify IFC models. It complements [AI Integration](/en/reference/ai) over REST: REST fits fine-grained attribute edits, the skill fits whole-model generation / large geometry changes.

## What it is

`skills/aiifc/` is a thin reference skill following the [Anthropic Agent Skills spec](https://github.com/anthropics/anthropic-sdk-python):

- **SKILL.md**: behavioral constitution (MUST 1–29) — skeleton-first, container required, world coordinates, opening discipline, three-layer validation, script contract (PARAMS + deterministic GlobalIds + build entry); design JSON is only a drafting aid for complex geometry.
- **references/**: 103 API pages, 8 component recipes (stairs / roof / windows / parapet / balcony), 13 runnable flows, 6 methodology references (SKD_OVERVIEW / MODELING_WORKFLOWS / DESIGN_JSON_SCHEMA / SPATIAL_QUALITY, etc.).
- **templates/**: copyable complete example scripts (e.g. `build_skeleton.py` minimal model).
- **requirements.txt**: Python deps for the flows (`ifcopenshell` / `ifcquery` / `numpy`, official PyPI releases, no local source dependency).

The layout derives from the SimpleCADAPI skill anatomy in this repo's history (`research/ifc/simplecadapi_skill_anatomy.md`), rewritten for the IFC domain: **modules split by action, four-level progressive disclosure, single responsibility per doc, connected by MUST clauses**.

## Building a model with the skill (agent view)

After loading the skill, write `ifcopenshell.api.run(...)` code in Pipeline order:

```
Skeleton (Project→Site→Building→Storey)
  → Elements (wall/slab/beam/column: entity + placement + representation + container)
  → Openings (openings + door/window fillings)
  → Data (type / material / property sets)
  → Export (model.write + ifcopenshell.validate)
```

For complex floor plans / irregular / multi-storey, first emit a **design JSON** (geometric intent, no coordinate math), normalize it through `design_builder.py`, then generate the build script — avoiding coordinate drift.

## Installing into your agent

The skill is an agent-agnostic directory bundle; any tool supporting the Agent Skills layout (opencode, Claude Code, Cursor, …) can load it:

```bash
# 1) Copy from the repo, or extract a release bundle
cp -r skills/aiifc ~/.config/opencode/skills/aiifc
# or build a distributable tar.gz
python tools/skill_pack_aiifc.py --archive   # produces skills/dist/aiifc.tar.gz
tar xzf skills/dist/aiifc.tar.gz -C ~/.config/opencode/skills/

# 2) Install runtime deps (needed by the flows)
uv pip install -r skills/aiifc/requirements.txt
```

## Relationship to the platform REST API

| Route | Use case | Entry |
|---|---|---|
| **REST editing API** | Edit attributes / psets of an existing model; pending → commit; version snapshots & diff | `:8100/models/{id}/...` (see [AI Integration](/en/reference/ai)) |
| **aiifc skill** | Build from scratch / large geometry changes; produce a complete IFC file | agent writes Python directly (`ifcopenshell.api`) |

They complement each other: the skill handles "generate / big-edit", the platform's commit / version / XKT-reconversion chain handles "persist & track".

## Packaging & distribution

- Packager: `tools/skill_pack_aiifc.py` (validates SKILL.md frontmatter / required paths / no noise, copies to `skills/dist/`, optionally tars).
- Artifact is agent-agnostic: `SKILL.md` + `references/` is the Agent Skills spec.
- CI (`skill (aiifc pack + flows smoke)` job) validates bundle integrity and runs flow smoke tests on every PR.

## License

`skills/aiifc/` declares **LGPL-3.0** (`license` field in SKILL.md frontmatter). Docs reference the [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) official documentation (LGPL-3.0).
