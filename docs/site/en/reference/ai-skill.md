# AI Skill (aiifc / aiplan / aidxf)

> The platform's AI authoring capabilities ship as **skill packages** on two tracks: the **IFC track** (`aiifc`) and the **plan→cad track** (`aiplan` + `aidxf` v3). Skills are aimed at AI agents — after loading one, the agent writes code / runs commands directly to author or modify models. This complements [AI Integration](/en/reference/ai) over REST: REST fits fine-grained attribute edits, skills fit whole-model generation / large-scale changes.

## Pipeline overview

The plan→cad track is the entry and middle section of the AI BIM pipeline: `aiplan` normalizes external material into a design brief, `aidxf` v3 turns that brief into drawings, and the downstream `bim` consumes it:

```
External material ──► aiplan ──┬─► plan.json (design brief) ────────► aidxf v3 ──► building.json + per-floor DXF ──► bim
                               └─► bim_supplement.json (BIM extras) ─────────────────────────────────────────────► bim
```

| Skill | Stage | Input | Output |
|---|---|---|---|
| `aiplan` | plan (pipeline entry) | No special requirements — external material (images/PPT/tech docs/user conversation) | `plan.json` + `bim_supplement.json` |
| `aidxfv3` | cad (pipeline middle) | `plan.json` (read-only) + additional user description | `building.json` + per-floor DXF |

## aiifc (IFC authoring/editing)

An **IfcOpenShell authoring skill** for AI agents — letting an agent write `ifcopenshell.api` code directly to create or modify IFC models.

### What it is

`skills/aiifc/` is a thin reference skill following the [Anthropic Agent Skills spec](https://github.com/anthropics/anthropic-sdk-python):

- **SKILL.md**: behavioral constitution (MUST 1–29) — skeleton-first, container required, world coordinates, opening discipline, three-layer validation, script contract (PARAMS + deterministic GlobalIds + build entry); design JSON is only a drafting aid for complex geometry.
- **references/**: 103 API pages, 8 component recipes (stairs / roof / windows / parapet / balcony), 13 runnable flows, 6 methodology references (SKD_OVERVIEW / MODELING_WORKFLOWS / DESIGN_JSON_SCHEMA / SPATIAL_QUALITY, etc.).
- **templates/**: copyable complete example scripts (e.g. `build_skeleton.py` minimal model).
- **requirements.txt**: Python deps for the flows (`ifcopenshell` / `ifcquery` / `numpy`, official PyPI releases, no local source dependency).

The layout derives from the SimpleCADAPI skill anatomy in this repo's history (`research/ifc/simplecadapi_skill_anatomy.md`), rewritten for the IFC domain: **modules split by action, four-level progressive disclosure, single responsibility per doc, connected by MUST clauses**.

### Building a model with aiifc (agent view)

After loading the skill, write `ifcopenshell.api.run(...)` code in Pipeline order:

```
Skeleton (Project→Site→Building→Storey)
  → Elements (wall/slab/beam/column: entity + placement + representation + container)
  → Openings (openings + door/window fillings)
  → Data (type / material / property sets)
  → Export (model.write + ifcopenshell.validate)
```

For complex floor plans / irregular / multi-storey, first emit a **design JSON** (geometric intent, no coordinate math), normalize it through `design_builder.py`, then generate the build script — avoiding coordinate drift.

## aiplan (plan stage: external material → design brief)

`skills/aiplan/` is the pipeline **entry** skill: it normalizes external material (images / PPT / tech docs / user conversation) into an executable architectural implementation plan, and confirms design intent through natural-language interaction (four progressive rounds: skeleton → geometry → function → structure/space, confirmed via the `question` tool). It does **not** draw DXF, write IFC, or do coordinate-level layout.

**Input**: no special requirements — external material and user descriptions in any form (step-00 ingest normalization → intent card).

**Output** — the schema source of truth lives in the bundled `references/schemas/`, i.e. these two files:

| Output | Contract source of truth | Consumed by |
|---|---|---|
| `plan.json` (design brief: what / where / which codes) | `skills/aiplan/references/schemas/plan.schema.json` | downstream cad (aidxf v3, read-only) |
| `bim_supplement.json` (BIM extras CAD cannot cover: roof / special structure / PSET) | `skills/aiplan/references/schemas/bim_supplement.schema.json` | downstream bim |

- **Landing**: outputs are produced in pairs — `aiplan land <plan> <bim> --outdir <dir>` lands them in `{workspace}/plan/` after gates (`aiplan validate` / `aiplan gate`) plus canon sha256 cross-references.
- **Self-contained**: schema / golden examples / vocabulary / building-type packs are all inline; only depends on `jsonschema`; independently portable with zero cross-skill runtime dependencies.

## aidxf v3 (plan→cad, the official version)

`skills/aidxf/` is the **official framework** for CAD generation — **future iterations build on this framework** (`v1` general DXF / `v2` floor-plan pipeline are legacy evolution, no longer the iteration baseline).

**Input**:
- `plan.json` (the design brief landed by aiplan, **read-only**, never modified)
- additional user description (requirement supplements)

**Output**:

| Output | Description |
|---|---|
| `building.json` | engineering drawings + bim interface (consumed by downstream bim) |
| per-floor `floor.dxf` | deliverable floor-plan drawings |

**Division of labor (LLM design × machine anchoring)**: the LLM declares `skeleton.json` (skeleton: zones / core / corridors / cut lines / blocks) and `rooms.json` (rooms: inherit zones / draw walls / labels) — saying where / how big / what's adjacent; **coordinates go to the machine**; derivation / anchoring / validation / rendering / retrieval are all machine work, and `aidxfv3 normalize` is the single coordinate-computation point.

**Pipeline (S0–S4)**: `preprocess` (plan.json → derived/ → checkpoint⓪) → `skeleton` (checkpoint①) → `rooms` (checkpoint②) → `details` (uniform door/window rules + column grid + annotations) → `deliver` (building.json + per-floor DXF + sealed rooms). Checkpoints are confirmed via the `question` tool; multi-zone (podium/tower on different levels) run as independent missions in parallel, orchestrated with `aidxfv3 state` plus interrupt recovery.

**Contract source of truth**: `references/schemas/` (plan copy / skeleton / rooms / building — **schema is the source of truth**); machine-command input/output schemas / boundary behavior / exit codes live in `references/machine_contract.md`.

**Dependencies**: `ezdxf` + `shapely` (see the bundled `requirements.txt`); self-contained with zero cross-skill runtime dependencies.

## Installing into your agent

Skills are agent-agnostic directory bundles; any tool supporting the Agent Skills layout (opencode, Claude Code, Cursor, …) can load them:

```bash
# 1) Copy from the repo, or extract a release bundle
cp -r skills/aiifc ~/.config/opencode/skills/aiifc
# or build distributable tar.gz bundles
python tools/skill_pack.py --archive   # produces skills/dist/aiifc.tar.gz (default skill: aiifc)
python tools/skill_pack.py --skill-dir skills/aiplan --archive        # aiplan
python tools/skill_pack.py --skill-dir skills/aidxfv/v3 --archive     # aidxfv3
tar xzf skills/dist/<name>.tar.gz -C ~/.config/opencode/skills/

# 2) Install runtime deps (per-skill requirements.txt)
uv pip install -r skills/aiifc/requirements.txt        # aiifc
uv pip install -r skills/aiplan/requirements.txt       # aiplan
uv pip install -r skills/aidxf/requirements.txt    # aidxfv3
```

## Relationship to the platform REST API

| Route | Use case | Entry |
|---|---|---|
| **REST editing API** | Targeted edits on an existing script (PARAMS staging / edit-call scalar rewrite); versions & diffs | `:8100/models/{id}/...` (IFC, see [AI Integration](/en/reference/ai)) |
| **aiifc skill** | Build IFC from scratch / large geometry changes / reproduce an uploaded IFC (bootstrap); produce a contract-conforming build script | agent writes Python directly (`ifcopenshell.api`) |
| **aiplan / aidxf v3 skills** | Full plan→cad chain: external material → design brief → per-floor DXF + building.json | agent runs `aiplan` / `aidxfv3` commands directly |

They complement each other: the skills handle "generate / big-edit", the platform's sandbox / version / XKT-reconversion chain handles "persist & track".

## Packaging & distribution

- Packager: `tools/skill_pack.py` (generic; validates SKILL.md frontmatter / required paths / no noise, copies to `skills/dist/`, optionally tars). `--skill <name>` defaults to `aiifc`; `--skill-dir <path>` packages any skill dir (aiplan / aidxfv3 go through this path).
- Artifact is agent-agnostic: `SKILL.md` + `references/` is the Agent Skills spec.
- CI (`skill (aiifc pack + flows smoke)` job) validates bundle integrity and runs flow smoke tests on every PR.

## License

- `skills/aiifc/` declares **LGPL-3.0** (`license` field in SKILL.md frontmatter). Docs reference the [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) official documentation (LGPL-3.0).
- `skills/aiplan/` and `skills/aidxf/` declare **MIT**.
