# AI_IFC

[中文说明](README.zh-CN.md)

A self-hosted, open-source **BIM review and editing platform** for IFC models — real IFC modification, semantic version diffing, and an AI-ready editing API shared by humans and agents.

> **Documentation: [https://0702hjj.github.io/AI_IFC/](https://0702hjj.github.io/AI_IFC/)** — quick start, viewer usage, development guide, REST/editing API and AI integration.

## What it does

- Upload IFC in the browser; review properties, spatial structure, issues and 3D pins.
- Really edit IFC attributes (override → pending → commit), with immutable version snapshots per commit.
- Compare versions with attribute-level semantic diffs (by GlobalId), rendered in the Diff Viewer.
- Expose the same REST editing API to humans (via the Go server) and AI agents (direct, with `provenance.source="AI"`).

## Quick start

See [Environment & Local Deployment](https://0702hjj.github.io/AI_IFC/guide/quickstart). Four components: `viewer/web` (React + xeokit), `viewer/server` (Go), `viewer/converter` (Node), `viewer/edit-service` (Python FastAPI + IfcOpenShell).

```bash
cd viewer/converter && npm install
cd ../edit-service && uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100 &
cd ../server && go run ./cmd/server &
cd ../web && npm install && npm run dev
```

Open http://localhost:5173 and upload `viewer/converter/test/fixtures/wall-with-opening-and-window.ifc`.

## Repository layout

```
viewer/            # active product: the IFC platform (web / server / converter / edit-service)
docs/site/         # public docs site (VitePress, published to GitHub Pages)
docs/internal/     # internal plans and team sync (not published)
docs/archive/      # archived SimpleCADAPI documentation
src/  skills/  examples/   # archived: SimpleCADAPI (SCAD), the repo's origin
```

## License

[AGPL-3.0-only](LICENSE) — inherited from the SimpleCADAPI fork and consistent with the AGPL-licensed xeokit stack. Third-party attributions and the archived-code boundary: [NOTICE](NOTICE).
