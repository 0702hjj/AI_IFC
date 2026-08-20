# AI Skills: Get & Install

> The platform's AI authoring capabilities ship as **skill packages**: a skill is a directory containing `SKILL.md` (entry point) plus reference docs/scripts. Drop one into your agent runtime to drive AI generation of IFC or CAD (DXF). Skills are decoupled from the rest of the platform — they work without deploying anything else.

## Available skills

| Skill | Purpose | License |
| --- | --- | --- |
| `aiifc` | IFC authoring/editing (IfcOpenShell reference bundle) | LGPL-3.0 |
| `aiplan` | Plan-stage skill (external material → plan.json + bim_supplement.json; feeds both cad and bim; no special input requirements) | MIT |
| `aidxfv3` | plan→cad floor-plan pipeline, official version (aiplan's plan.json → building.json + per-floor DXF; the sole iteration baseline — v1/v2 retired and removed) | MIT |
| `aiblueprint-mcp` | MCP server for interactive DXF inspection/editing/measure/preview | MIT |
| `aibim-orchestrator` | Main-agent orchestration prompt pack (intent routing + sub-agent contracts + plan→cad→ifc relay data contract) | Apache-2.0 |

Detailed input/output contracts for each skill live in [AI Skill (aiifc / aiplan / aidxfv)](/en/reference/ai-skill); each skill's history lives in its bundled `CHANGELOG.md` (existing skills are all at `0.1.0`).

## Download

Grab `<name>-<version>.tar.gz` (e.g. `aiifc-0.1.0.tar.gz`) from the GitHub Releases page; or package one yourself from the repo:

```bash
python tools/skill_pack.py --skill aiifc --archive
python tools/skill_pack.py --skill aidxfv3 --skill-dir skills/aidxfv/v3 --archive
```

Artifacts land in `skills/dist/`.

## Install

Extract into the agent runtime's skills directory:

- **opencode**: user-level `~/.agents/skills/<name>/`, or project-level `<project>/.opencode/skill/<name>/` (singular `skill`)
- **Claude Code**: `~/.claude/skills/<name>/`

Once installed, the runtime indexes `name`/`description` from `SKILL.md` automatically — no extra registration needed.

## Runtime dependencies

- **aiifc**: Python with `ifcopenshell` / `ifcquery` / `numpy` (see the bundled `requirements.txt`); for pairing with the `services/ifc` edit service see [services/ifc Standalone](/en/guide/services-ifc).
- **aidxfv3**: Python with `ezdxf` + `shapely` (see the bundled `requirements.txt`).
- **aiplan**: only `jsonschema` (see the bundled `requirements.txt`).
- **aiblueprint-mcp**: MCP-server form; dependencies in its bundled `requirements.txt`, wire it up via the bundled README / opencode.json.

## Relationship to the platform

Skills are the **AI-side** entry point (the agent writes build scripts / calls tools directly); `services/ifc` is the **server-side** runtime (sandboxed execution, version snapshots, semantic diff). They pair together but are fetched and deployed independently — one-off generation needs only the skill; version/diff/dual-role editing APIs need [services/ifc](/en/guide/services-ifc).
