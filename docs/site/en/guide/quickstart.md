# Environment & Local Deployment

## Dependencies

| Dependency | Version | Purpose | Required |
| --- | --- | --- | --- |
| Go | 1.26+ | server | yes |
| Node.js | 18+ | converter (`npm install` once, no daemon) | yes |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service | for editing/diff; browsing works without it |
| PostgreSQL | 14+ | issues/changes/overrides persistence | optional (file storage by default) |

> **Python dependencies**: edit-service depends on `ifcopenshell` / `ifcdiff` / `ifcquery` (all official PyPI releases, aligned with IfcOpenShell 0.8.5); `uv sync` installs them directly. No local IfcOpenShell source checkout needed.

## Docker Compose (recommended)

Docker only; one command starts the full stack (web / server / converter / edit-service):

```bash
cp .env.example .env   # optional: every entry has a default
docker compose up --build
```

Open `http://localhost:8080`. Data lives in a named volume (`aiifc-data`); models survive `down`/`up`.

With PostgreSQL (issues/changes/overrides via PG, tables created automatically):

```bash
# set in .env: VIEWER_PG_DSN=postgres://aiifc:aiifc@postgres:5432/aiifc?sslmode=disable
docker compose --profile pg up -d
```

Tunables (ports, `DATA_DIR`, `VIEWER_PG_DSN`, …) are listed in `.env.example`.

## Start (four terminals, no Docker)

```bash
# 0. One-time dependency install
cd converter && npm install
cd ../web && npm install
cd ../services/ifc && uv sync

# 1. edit-service (:8100) — VIEWER_DATA_DIR must point to the absolute path of data
cd services/ifc
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100

# 2. Go server (:8090)
cd server && go run ./cmd/server

# 3. web (:5173)
cd web && npm run dev
```

Open `http://localhost:5173` and you are ready. Full configuration: [Configuration](/en/guide/configuration).

## Verification

```bash
# End-to-end smoke (server must be running; the edit-flow section skips when edit-service is unreachable)
./scripts/smoke.sh

# Per-layer tests
cd server && go test ./...
cd services/ifc && uv run --group dev pytest
cd web && npm test
cd converter && npm test
```

> Note: upload, conversion and review do not need edit-service or PostgreSQL; editing, versions and diff do.
