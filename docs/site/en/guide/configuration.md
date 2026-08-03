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
