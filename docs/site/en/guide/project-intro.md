# Project Introduction

AI_IFC is a **self-hosted, open-source** IFC model review and editing platform. It was forked from SimpleCADAPI, but the active product is the IFC platform under `viewer/`; SimpleCADAPI-related code was moved on 2026-08-06 to the private archive repo [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive), see [License & third-party components](/project/license) (Chinese).

## Positioning

- **What it is**: a self-hosted IFC review + editing platform — script-as-source editing (every change lands on the Python build script), semantic version diffing, and an editing API shared by humans and AI agents.
- **Who it is for**: self-hosted BIM teams (intranet or personal); developers building IFC tooling; researchers who need an "AI-pluggable BIM editing base".
- **Current capability**: functional end-to-end — upload → convert → 3D review → issues → script editing (locate / rewrite / sandbox / staging) → big versions → version diff.

## Capability boundaries

**Delivered:**

- IFC upload with queued conversion (XKT geometry + semantic metadata).
- 3D review: model tree, property inspection, visibility tools, section planes, measurements, NavCube.
- Issues and 3D pins: creation with camera state + screenshot, status workflow, click-to-locate.
- Script editing (script-as-source): the Python build script is the single source of truth — select an element to locate its script callsite (ScriptMap), edit via the PARAMS form or libcst scalar rewrite (edit-call), sandbox validation, a 10-step staging ring, and paired big-version snapshots (script + map; only the latest IFC is materialized, history rebuilt on demand).
- Version snapshots and attribute-level semantic diffs (Diff Viewer).
- One editing API shared by humans and AI, distinguished by `UI` / `AI` / `USER` provenance; an MCP server thinly wraps the editing API (stdio).
- Optional PostgreSQL storage (issues / overrides / change log); file storage runs with zero external dependencies when unconfigured.

**Not delivered (see [Known limitations](/project/known-limits) and [Roadmap](/project/roadmap), Chinese):**

- Multi-user/auth; geometric diff; Docker Compose one-command deployment; English versions of the Viewer usage and detailed development pages.

## Four-component architecture

| Component | Tech | Responsibility |
| --- | --- | --- |
| `web` | React 19 + xeokit | Model library, 3D review, script editing (PARAMS form + script editor + locate), issues, Diff Viewer |
| `server` | Go 1.26 (stdlib + pgx/v5) | Upload/conversion queue, REST API, edit orchestration, storage abstraction |
| `converter` | Node CLI (web-ifc + xeokit-convert) | IFC → XKT + metadata.json |
| `edit-service` | Python FastAPI + IfcOpenShell (+ ifcdiff / ifcquery, PyPI) | Script sandbox execution, version snapshots, ScriptMap locate, semantic diffs |

The three-language stack is an ecosystem reality rather than a design preference: each language binds the only or best IFC library in that ecosystem. Services communicate over REST and subprocesses, and any component can be replaced independently.

Detailed architecture: [Architecture](/en/development/architecture).
