# Project Introduction

AI_IFC is a **self-hosted, open-source** IFC model review and editing platform. It was forked from SimpleCADAPI, but the active product is the IFC platform under `viewer/`; SimpleCADAPI-related code was moved on 2026-08-06 to the private archive repo [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive), see [License & third-party components](/project/license) (Chinese).

## Positioning

- **What it is**: a self-hosted IFC review + editing platform — real IFC attribute edits, semantic version diffing, and an editing API shared by humans and AI agents.
- **Who it is for**: self-hosted BIM teams (intranet or personal); developers building IFC tooling; researchers who need an "AI-pluggable BIM editing base".
- **Current capability**: functional end-to-end — upload → convert → 3D review → issues → property editing → commit → version diff.

## Capability boundaries

**Delivered:**

- IFC upload with queued conversion (XKT geometry + semantic metadata).
- 3D review: model tree, property inspection, visibility tools, section planes, measurements, NavCube.
- Issues and 3D pins: creation with camera state + screenshot, status workflow, click-to-locate.
- Property editing: whitelisted overrides (display layer) and the two-phase pending → commit real IFC edit flow.
- Version snapshots and attribute-level semantic diffs (Diff Viewer).
- One editing API shared by humans and AI, distinguished by `UI` / `AI` provenance.
- Optional PostgreSQL storage (issues / overrides / change log); file storage runs with zero external dependencies when unconfigured.

**Not delivered (see [Known limitations](/project/known-limits) and [Roadmap](/project/roadmap), Chinese):**

- Multi-user/auth; AI IFC generation itself; MCP wrapper; geometric diff; Docker Compose one-command deployment; fully bilingual site; automated OpenAPI generation (partially delivered, see [OpenAPI Files](/en/reference/openapi)).

## Four-component architecture

| Component | Tech | Responsibility |
| --- | --- | --- |
| `web` | React 19 + xeokit | Model library, 3D review, property editing, issues, Diff Viewer |
| `server` | Go 1.26 (stdlib + pgx/v5) | Upload/conversion queue, REST API, edit orchestration, storage abstraction |
| `converter` | Node CLI (web-ifc + xeokit-convert) | IFC → XKT + metadata.json |
| `edit-service` | Python FastAPI + IfcOpenShell (+ ifcdiff / ifcquery, PyPI) | Real IFC edits, pending/commit, version snapshots, semantic diffs |

The three-language stack is an ecosystem reality rather than a design preference: each language binds the only or best IFC library in that ecosystem. Services communicate over REST and subprocesses, and any component can be replaced independently.

Detailed architecture: [Architecture](/en/development/architecture).
