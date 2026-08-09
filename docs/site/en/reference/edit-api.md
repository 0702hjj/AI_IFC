# IFC Editing API

The edit-service (Python FastAPI, default `:8100`) is the **single reference** for IFC editing endpoints. Path parameters: `id` matches `^m_[0-9a-f]{16}$`; `guid` is an IFC GlobalId. Unless noted, error responses use the FastAPI shape `{"detail": ...}`.

> **Direct editing retired (2026-08-08)**: with script-as-source unified editing, every change lands on the build script. The former L1 direct-edit endpoints (`PUT/DELETE /models/{id}/entities/...`, `GET .../editable-schema`, `POST /models/{id}/commit`) **return 410 Gone** (permanent retirement, not 404); the historical implementation can be recovered from git history (anchor `fb55a8a`). For the live editing surface see [Script editing & version diff](/en/reference/design-edit).

## Endpoint catalog

### GET /health

Health check, responds `{"status": "ok"}`.

### Direct-edit endpoints (410 Gone)

| Endpoint | Retirement note |
| --- | --- |
| `PUT /models/{id}/entities/{guid}` | Edit the build script instead (`PUT /script` or `POST /script/edit-call`) |
| `GET /models/{id}/entities/{guid}/editable-schema` | No typed edit form without direct editing |
| `DELETE /models/{id}/entities/{guid}` | Delete elements via script edits |
| `POST /models/{id}/commit` | `script/save` is the only version checkpoint |

All return `410 {"detail": "direct IFC editing retired: edit the build script (script-as-source)"}`.

### GET /models/{id}/pending

Lists current pending changes (`[]` when empty). After the retirement, pending only serves as script-run replay bookkeeping (internal) and no longer carries user edits. Note: GET pending/history **do not validate the model**; write paths and versions/diff do.

### DELETE /models/{id}/pending

Discards all pending changes: unloads and reloads the model from disk. Responds `{"discarded": <count>}`; 404 when the model does not exist.

### GET /models/{id}/history

Persistent editing history (includes `operation`), stored at `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`; `[]` when empty. After the retirement the history is read-only legacy data; new entries come from `POST /models/{id}/user-edits` (registration of externally edited IFC/DXF).

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

For script-backed models only the latest big version's IFC is materialized on disk; historical versions are rebuilt from their scripts on demand (see [Versions & Diff Viewer](/en/viewer/versions-diff)).

### POST /models/{id}/diff

Body: `{"base": "v1", "target": "v2"}` (`target` may be `"current"` for the live upload). Response:

```json
{
  "base": "v1",
  "target": "v2",
  "added": ["<guid>", ...],
  "removed": ["<guid>", ...],
  "changed": [{"guid": "...", "changes": [{"field": "...", "old": ..., "new": ...}]}]
}
```

Missing version → 404; missing `base`/`target` → 422. Diff is attribute-level (no geometric diff), see [Versions & Diff Viewer](/en/viewer/versions-diff).

### POST /models/{id}/diff/upload

Upload comparison: `multipart/form-data` field `file` (an IFC to compare) diffed against the current model state, attribute-level by GlobalId. The response adds a `labels` map (guid → readable name/type) to the `POST /diff` shape; `base` is always `"current"`, `target` always `"upload"`. Nothing is persisted or cached. Invalid IFC → 422.

### Script editing endpoints

`GET/PUT /models/{id}/script`, `script/params`, `script/undo|redo|discard`, `script/run`, `script/save`, `script/rollback`, `script/diff`, `script/staging/diff`, `script/locate`, `script/edit-call`, `GET /models/{id}/scripts` — semantics and contracts in [Script editing & version diff](/en/reference/design-edit); machine-readable schema in the [Editing API reference (generated)](/reference/edit-api-reference) (Chinese).

## Via the Go proxy

The Go server (default `:8090`) exposes endpoints under `/api/v1`:

- Script editing endpoints are proxied one-to-one: `/api/v1/models/{id}/script[/...]` (including `script/locate`, query passed through); after a successful run/save/rollback the Go side queues XKT reconversion. `script/edit-call` is **not** proxied — edit-service direct only.
- Read-only/compare endpoints stay under `/api/v1/models/{id}/edit/...`: `POST .../edit/diff` (→ `POST /models/{id}/diff`), `GET .../edit/pending|history|versions`, `DELETE .../edit/pending`.
- The direct-edit proxy routes (`PUT/DELETE .../edit/entities/{guid}`, `POST .../edit/commit`, `editable-schema`) were removed with the retirement.

Differences from direct access: responses are wrapped in `{code, message, data}`; error mapping: 404 → 40400, 409 → 40900, 422 → 40001, anything else (including unreachable) → 50200.
