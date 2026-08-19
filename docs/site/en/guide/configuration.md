# Configuration

## Go server (`server/server_config.json`)

Paths are resolved relative to the process working directory (not the executable).

| key | default | env override | description |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | listen address |
| `dataDir` | `../data` | — | data directory (**must equal edit-service's VIEWER_DATA_DIR**) |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | converter invocation |
| `maxUploadMB` | `200` | — | upload limit |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | enables PostgreSQL (auto-creates tables); empty = file storage |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service URL |
| `cadServiceURL` | `http://127.0.0.1:8200` | `VIEWER_CAD_SERVICE_URL` | cad-edit-service URL (DXF models routed by kind) |
| `apiToken` | `""` | `VIEWER_API_TOKEN` | Bearer token auth; **empty = disabled** (local development only), **required for production / multi-user deployments**; when set, all endpoints except exempt paths require `Authorization: Bearer <token>` |
| `corsOrigins` | `http://localhost:5173,http://localhost:8080` | `VIEWER_CORS_ORIGINS` | CORS origin whitelist, comma-separated; non-whitelisted Origins are not reflected in `Access-Control-Allow-Origin` |

```json
{
  "host": "127.0.0.1",
  "port": 8090,
  "dataDir": "../data",
  "nodeBin": "node",
  "converterScript": "../converter/convert.js",
  "maxUploadMB": 200,
  "pgDSN": "",
  "editServiceURL": "http://127.0.0.1:8100"
}
```

## Auth & CORS

- Auth is off by default (`apiToken` empty), suitable only for local single-machine development. **Production / multi-user deployments must set `apiToken` (or env `VIEWER_API_TOKEN`)** — the editing API executes build scripts in a server-side sandbox (script execution is code execution), so exposing it without auth is equivalent to an open remote-code-execution endpoint.
- When enabled, every endpoint requires `Authorization: Bearer <token>` (the Bearer scheme is enforced; a bare token is rejected) except: OPTIONS preflights, `GET /v1/models/{id}/model.xkt`, `GET /v1/models/{id}/metadata.json`, `GET /v1/models/{id}/issues/{file}` (xeokit and `<img>` tags cannot send headers, so these stay anonymously readable). 401 responses use the standard envelope with error code `40100`.
- **Browser UI**: the web app automatically attaches the token stored in localStorage (key `aiifc_token`) to every API request. If no token is stored or it becomes invalid, the first 401 pops up a token input dialog; saving retries the original request. The chat SSE event stream (EventSource cannot send custom headers) passes the token via a `?token=` query parameter (the server only allows this fallback on the events path).
- With docker compose, set `VIEWER_API_TOKEN` in `.env` (see `.env.example`); compose passes it through to the server container.
- edit-service (:8100) and cad-edit-service (:8200) have **no auth of their own** and rely on network isolation: keep them bound to `127.0.0.1` and never expose them; AI agents connecting directly to :8100/:8200 bypass the Go server token check.
- CORS is tightened from `*` to a whitelist (two local dev ports by default); add deployment origins via `corsOrigins` / `VIEWER_CORS_ORIGINS`.

## edit-service

| Environment variable | default | description |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | data directory (relative to the process working directory); **must point to the same directory as the server `dataDir`** or edits return 404 |
| `EDIT_SERVICE_PORT` | `8100` | listen port |

## cad-edit-service (DXF editing, structurally identical to edit-service)

| Environment variable | default | description |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | data directory; **must match the server `dataDir` and edit-service `VIEWER_DATA_DIR`** |
| `AIDXF_FLOWS_DIR` | `flows` (relative to service root) | DXF sandbox contract layer directory (`services/cad/flows`) |
| `CAD_SERVICE_PORT` | `8200` | listen port |

In docker compose the service is named `cad-edit-service` (the server reaches it via `VIEWER_CAD_SERVICE_URL=http://cad-edit-service:8200`, already wired in compose).

## PostgreSQL (optional)

- Without `pgDSN` / `VIEWER_PG_DSN`, issues / overrides / change log use file storage with zero external dependencies.
- When configured, the server auto-creates `issues` / `changes` / `overrides` tables at startup; model files (uploads / models / version snapshots) always stay on the filesystem.
- Tests need `VIEWER_TEST_PG_DSN` pointing to a **dedicated test database** (tests DROP tables).

## Ports

Defaults: server `8090`, edit-service `8100`, cad-edit-service `8200`, web dev server `5173`.
