# Configuration

## Go server (`viewer/server/server_config.json`)

Paths are resolved relative to the process working directory (not the executable).

| key | default | env override | description |
| --- | --- | --- | --- |
| `host` / `port` | `127.0.0.1` / `8090` | — | listen address |
| `dataDir` | `../data` | — | data directory (**must equal edit-service's VIEWER_DATA_DIR**) |
| `nodeBin` / `converterScript` | `node` / `../converter/convert.js` | — | converter invocation |
| `maxUploadMB` | `200` | — | upload limit |
| `pgDSN` | `""` | `VIEWER_PG_DSN` | enables PostgreSQL (auto-creates tables); empty = file storage |
| `editServiceURL` | `http://127.0.0.1:8100` | `VIEWER_EDIT_SERVICE_URL` | edit-service URL |
| `apiToken` | `""` | `VIEWER_API_TOKEN` | Bearer token auth; **empty = disabled** (zero-config single-machine default); when set, all endpoints except exempt paths require `Authorization: Bearer <token>` |
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

- Auth is off by default (`apiToken` empty) for single-machine localhost use. **If you change `host` to a non-loopback address, set `apiToken` (or env `VIEWER_API_TOKEN`).**
- When enabled, every endpoint requires `Authorization: Bearer <token>` except: OPTIONS preflights, `GET /v1/models/{id}/model.xkt`, `GET /v1/models/{id}/metadata.json`, `GET /v1/models/{id}/issues/{file}` (xeokit and `<img>` tags cannot send headers, so these stay anonymously readable). 401 responses use the standard envelope with error code `40100`.
- edit-service (:8100) has **no auth of its own** and relies on network isolation: keep it bound to `127.0.0.1` and never expose it; AI agents connecting directly to :8100 bypass the Go server token check.
- CORS is tightened from `*` to a whitelist (two local dev ports by default); add deployment origins via `corsOrigins` / `VIEWER_CORS_ORIGINS`.

## edit-service

| Environment variable | default | description |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | data directory (relative to the process working directory); **must point to the same directory as the server `dataDir`** or edits return 404 |
| `EDIT_SERVICE_PORT` | `8100` | listen port |

## PostgreSQL (optional)

- Without `pgDSN` / `VIEWER_PG_DSN`, issues / overrides / change log use file storage with zero external dependencies.
- When configured, the server auto-creates `issues` / `changes` / `overrides` tables at startup; model files (uploads / models / version snapshots) always stay on the filesystem.
- Tests need `VIEWER_TEST_PG_DSN` pointing to a **dedicated test database** (tests DROP tables).

## Ports

Defaults: server `8090`, edit-service `8100`, web dev server `5173`.
