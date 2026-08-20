# Environment & Local Deployment

Deployment shape: runs directly on the host (no Docker). The Go server serves the built web assets itself; edit-service / cad-edit-service run as host processes.

## Dependencies

| Dependency | Version | Purpose | Required |
| --- | --- | --- | --- |
| Go | 1.26+ | server | yes |
| Node.js | 22+ | converter (`npm install` once, no daemon) + web build | yes |
| Python + [uv](https://docs.astral.sh/uv/) | 3.10+ | edit-service / cad-edit-service | for editing/diff; browsing works without it |
| Linux + bubblewrap | — | script sandbox backend (bwrap) | required in production; without it the sandbox fails closed (run/save rejected) |
| PostgreSQL | 14+ | issues/changes/overrides persistence | optional (file storage by default) |

> **Python dependencies**: edit-service depends on `ifcopenshell` / `ifcdiff` / `ifcquery` (all official PyPI releases, aligned with IfcOpenShell 0.8.5); `uv sync` installs them directly. No local IfcOpenShell source checkout needed.
>
> **Installing bubblewrap**: Debian/Ubuntu `sudo apt install bubblewrap`; RHEL-family `sudo dnf install bubblewrap`. bwrap works natively in user space on the host. On dev machines without bwrap you may set `ALLOW_RLIMIT_FALLBACK=1` to degrade to the rlimit sandbox (weaker FS/network isolation) — **never set it in production**.

## Start (development, four terminals)

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

## Production deployment (host)

Production is single-port: the Go server serves the built web assets and proxies the API; browsers only talk to the server port (default :8090).

```bash
# 1. Build the frontend (output in web/dist)
cd web && npm ci && npm run build

# 2. Build and start the server (serves ../web/dist by default; override with the
#    webDist key in server_config.json or the VIEWER_WEB_DIST env var)
cd ../server && go build -o server ./cmd/server && ./server

# 3. Start the business services (edit-service :8100 / cad-edit-service :8200, bound to 127.0.0.1)
cd ../services/ifc && uv sync && VIEWER_DATA_DIR=/srv/aiifc/data uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
cd ../services/cad && uv sync && VIEWER_DATA_DIR=/srv/aiifc/data uv run uvicorn app.main:app --host 127.0.0.1 --port 8200
```

> **Production deployments**: `VIEWER_API_TOKEN` is **required** for any production / multi-user setup (pass it to the server as an environment variable). Threat model: the editing API executes build scripts in a server-side sandbox — **script execution is code execution**; running with auth disabled (empty token) is only acceptable for local single-machine development.

PostgreSQL (optional): install PostgreSQL 14+ on the host and pass `VIEWER_PG_DSN=postgres://user:pass@127.0.0.1:5432/aiifc` to the server (tables are created automatically).

### Minimal systemd units

```ini
# /etc/systemd/system/aiifc-server.service
[Unit]
Description=AI_IFC Go server
After=network.target

[Service]
WorkingDirectory=/opt/AI_IFC/server
Environment=VIEWER_API_TOKEN=replace-with-strong-random-string
ExecStart=/opt/AI_IFC/server/server -config server_config.json
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/aiifc-ifc.service (cad is identical: WorkingDirectory services/cad, port 8200)
[Unit]
Description=AI_IFC edit-service
After=network.target

[Service]
WorkingDirectory=/opt/AI_IFC/services/ifc
Environment=VIEWER_DATA_DIR=/opt/AI_IFC/data
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8100
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Note: `VIEWER_DATA_DIR` (both Python services) and the server `dataDir` (server_config.json) must point to the **same directory**, writable by whichever user the services run as.

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
