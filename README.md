# AI_IFC

[中文说明](README.zh-CN.md)

A self-hosted, open-source **BIM review and editing platform** for IFC models — script-as-source editing (every edit rewrites the Python build script), semantic version diffing, and an AI-ready editing API shared by designers and agents.

> **Documentation: [https://0702hjj.github.io/AI_IFC/](https://0702hjj.github.io/AI_IFC/)** — quick start, viewer usage, development guide, REST/editing API and AI integration.

## Key Advantages

| | |
|---|---|
| **Script-as-source editing** | The Python build script is the single source of truth; every web edit rewrites the script (locate callsite → PARAMS/libcst rewrite → sandbox-validated → staged), and each save snapshots script + ScriptMap as an immutable big version. |
| **Semantic version diff** | Attribute-level diff keyed by GlobalId (added / removed / changed), rendered in the Diff Viewer with old → new detail — no geometry noise. |
| **One API, two roles** | The same REST editing API for designers (via the Go server) and AI agents (direct, with `provenance.source="AI"`). |
| **AI authoring skill** | An agent-agnostic `aiifc` skill lets AI write `ifcopenshell.api` code to build or modify models from natural language. |
| **Self-hosted & open** | AGPL-3.0, four components (web / server / converter / edit-service), file or PostgreSQL storage, single-machine friendly. |

## What it does

- Upload IFC in the browser; review properties, spatial structure, issues and 3D pins.
- Edit by editing the build script: locate an element's callsite from the viewer, change it via the PARAMS form or script editor, sandbox-validated and staged; each save produces an immutable big version.
- Compare versions with attribute-level semantic diffs (by GlobalId), rendered in the Diff Viewer.
- Expose the same REST editing API to designers (via the Go server) and AI agents (direct, with `provenance.source="AI"`).
- Ship an AI authoring skill (`skills/aiifc/`) so agents can generate or heavily modify IFC models, complementing the REST editing API.

## Architecture

```
Browser (React + xeokit) ──► Go server ──► edit-service (FastAPI + IfcOpenShell)
                                  │                └─ script sandbox + versions + diff
                                  ├─► converter (Node, IFC → XKT)
AI agent ──► REST editing API ────┘
          └─► aiifc skill (write ifcopenshell.api code directly)
```

## Screenshots

| Model library | 3D viewer |
|---|---|
| ![Model library](docs/site/public/screenshots/library.png) | ![3D viewer](docs/site/public/screenshots/viewer.png) |

| Property editing | Version diff | AI chat |
|---|---|---|
| ![Property editing](docs/site/public/screenshots/properties.png) | ![Version diff](docs/site/public/screenshots/diff.png) | ![AI chat](docs/site/public/screenshots/chat.png) |

## Quick start

See [Environment & Local Deployment](https://0702hjj.github.io/AI_IFC/guide/quickstart). Four components: `web` (React + xeokit), `server` (Go), `converter` (Node), `services/ifc` (Python FastAPI + IfcOpenShell).

One-command start (recommended, Docker only): `docker compose up --build` → open http://localhost:8080 (tunables in `.env.example`).

Manual start:

```bash
cd converter && npm install
cd ../edit-service && uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 &
cd ../server && go run ./cmd/server &
cd ../web && npm install && npm run dev
```

Open http://localhost:5173 and upload `converter/test/fixtures/wall-with-opening-and-window.ifc`.

## AI: two complementary routes

| Route | For | Entry |
|---|---|---|
| [REST editing API](https://0702hjj.github.io/AI_IFC/reference/ai) | Script-as-source edits: stage/run/save build scripts, locate callsites by guid, libcst scalar rewrite (edit-call), version and diff | `:8100/models/{id}/...` |
| [AI Skill (aiifc)](https://0702hjj.github.io/AI_IFC/reference/ai-skill) | Building models from scratch / large geometry changes | `skills/aiifc/` — the agent writes a complete Python **build script** (top-level `PARAMS` + `build()`); the script is the single source of truth that maps one-to-one to the IFC, and is versioned and diffed (script-as-source) |

The skill is agent-agnostic (opencode, Claude Code, Cursor, …). Bundle it with:

```bash
python tools/skill_pack.py --archive   # produces skills/dist/aiifc.tar.gz (default skill: aiifc)
python tools/skill_pack.py --skill-dir skills/aidxfv/v1 --archive   # any skill dir (here: CAD v1)
```

## Repository layout

The platform provides **two peer logic legs** — AI-generated IFC and AI-generated CAD — plus an optional Agent workflow control. Each logic leg pairs a distributable **skill** with a **services/** business-logic core (diff + frontend-facing edit API); the frontend, Go gateway, converter and PostgreSQL are shared, optional runtime. See [platform framework spec](docs/superpowers/specs/2026-08-11-platform-framework-design.md).

```
AGENTS.md          # human-AI collaboration contract (agent entry point)
skills/aiifc/      # AI authoring skill — IFC leg (distributable, agent-agnostic)
skills/aidxfv/     # AI authoring skill — CAD leg (v1 general DXF / v2 floor-plan pipeline)
services/ifc/      # IFC business-logic core: diff + script-as-source editing API
services/cad/      # CAD business-logic core: diff + editing API (to build, peer of services/ifc)
web/               # optional frontend (React 19 + xeokit, :5173)
server/            # Go gateway (:8090, REST entry + orchestration + storage abstraction)
converter/         # Node converter (IFC → XKT)
mcp/               # MCP bridge (optional, thin wrapper over services/ifc)
scripts/           # end-to-end smoke test (smoke.sh)
data/              # runtime data (gitignored, shared by services/ifc and server)
AI_CAD/            # CAD skill domain + research (aidxfv moved into skills/aidxfv; research stays)
tools/             # skill packager (skill_pack.py)
docs/site/         # public docs site (VitePress, published to GitHub Pages)
docs/work/         # work-item board (audit, plans, trackable items)
docs/internal/     # internal team docs (not published)
docs/superpowers/  # design specs and implementation plans (process artifacts)
examples/          # IFC-era example scripts
```

`services/ifc/` is the IFC business-logic core; `skills/aidxfv/v1|v2` are the CAD skill entry points (moved from `AI_CAD/skills/aidxfv*`); `web|server|converter|mcp|scripts|data` are the shared optional runtime (moved out of the former `viewer/`).

The SimpleCADAPI heritage code (`src/`, `skills/simplecadapi/`, SCAD-era packaging files) was moved to the private archive repo [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive) on 2026-08-06; this repo no longer contains it.

## License

[AGPL-3.0-only](LICENSE) — inherited from the SimpleCADAPI fork and consistent with the AGPL-licensed xeokit stack. Third-party attributions and the archived-code boundary: [NOTICE](NOTICE). The `skills/aiifc/` skill itself declares **LGPL-3.0** (reference docs for the LGPL-licensed IfcOpenShell).
