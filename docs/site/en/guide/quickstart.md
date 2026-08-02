# Environment & Local Deployment

## Dependencies

| Dependency | Version | Purpose | Required |
| --- | --- | --- | --- |
| Go | 1.26+ | server | yes |
| Node.js | 18+ | converter (`npm install` once, no daemon) | yes |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | for editing/diff; browsing works without it |
| PostgreSQL | 14+ | issues/changes/overrides persistence | optional (file storage by default) |
| IfcOpenShell source checkout | v0.8 | local editable dependency of ifcdiff | currently required (see below) |

> **ifcdiff dependency note**: `viewer/edit-service/pyproject.toml` currently references the IfcOpenShell source checkout (`src/ifcdiff`) next to this repo as a local editable dependency. Before running edit-service you need an IfcOpenShell v0.8 checkout in a sibling directory. This is a documented deployment limitation; self-containment (vendor or git source) is tracked in the [Roadmap](/project/roadmap) (Chinese).

## Start (four terminals)

```bash
# 0. One-time dependency install
cd viewer/converter && npm install
cd ../web && npm install
cd ../edit-service && uv sync

# 1. edit-service (:8100) — VIEWER_DATA_DIR must point to the absolute path of viewer/data
cd viewer/edit-service
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server (:8090)
cd viewer/server && go run ./cmd/server

# 3. web (:5173)
cd viewer/web && npm run dev
```

Open `http://localhost:5173` and you are ready. Full configuration: [Configuration](/en/guide/configuration).

## Verification

```bash
# End-to-end smoke (server must be running; the edit-flow section skips when edit-service is unreachable)
cd viewer && ./scripts/smoke.sh

# Per-layer tests
cd viewer/server && go test ./...
cd viewer/edit-service && uv run pytest
cd viewer/web && npm test
cd viewer/converter && npm test
```

> Note: upload, conversion and review do not need edit-service or PostgreSQL; editing, versions and diff do.
