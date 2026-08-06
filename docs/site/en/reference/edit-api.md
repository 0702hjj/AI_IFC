# IFC Editing API

The edit-service (Python FastAPI, default `:8100`) is the **single reference** for IFC editing endpoints. Path parameters: `id` matches `^m_[0-9a-f]{16}$`; `guid` is an IFC GlobalId. Unless noted, error responses use the FastAPI shape `{"detail": ...}`.

## Endpoint catalog

### GET /health

Health check, responds `{"status": "ok"}`.

### PUT /models/{id}/entities/{guid}

Applies an edit to the in-memory model and records one pending change (**no disk write**). Full validation happens before any application (atomic per request): any failure produces zero modifications.

Body (`EditBody`):

```json
{
  "type": "object",
  "properties": {
    "fields": {"type": "object", "additionalProperties": true, "description": "direct entity attributes (Name/Description etc.)"},
    "psets": {"type": "object", "additionalProperties": {"type": "object", "additionalProperties": true}, "description": "pset name → {attribute: new value}; psets are created when missing"},
    "author": {"type": "string", "default": "local-user"},
    "provenance": {"type": "object", "properties": {"source": {"type": "string", "enum": ["UI", "AI"], "default": "UI"}}}
  }
}
```

Response 200 (a pending entry that also appears in pending and in history after commit):

```json
{
  "id": "e_<12hex>",
  "guid": "...",
  "changes": [{"field": "Name", "oldValue": "...", "newValue": "..."}],
  "author": "ai-agent",
  "provenance": {"source": "AI"},
  "timestamp": "<ISO8601 UTC>"
}
```

`changes[].field`: direct attributes use the attribute name; pset attributes use `PsetName.attribute`; `oldValue` is the real IFC value (`null` when the pset attribute did not exist).

Error codes: 404 model or guid not found; 422 both `fields`/`psets` empty, unknown attribute, unsupported value type, or a type mismatch with the IFC attribute.

### GET /models/{id}/pending

Lists current pending changes (`[]` when empty). Note: GET pending/history **do not validate the model**; write paths and versions/diff do.

### DELETE /models/{id}/pending

Discards all pending changes: unloads and reloads the model from disk. Responds `{"discarded": <count>}`; 404 when the model does not exist.

### POST /models/{id}/commit

Atomically writes all pending changes (file lock) → version snapshot → appends history (each entry gets `operation`) → clears pending.

Optional body: `{"operation": "update" | "migrate"}`, default `"update"`; `migrate` is passed by the Go override migration. Response 200 `{"committed": <count>, "entries": [...]}`; 409 without pending; 404 when the model does not exist.

### GET /models/{id}/history

Persistent editing history (includes `operation`), stored at `{VIEWER_DATA_DIR}/models/{id}/edit-history.json`; `[]` when empty.

### GET /models/{id}/versions

```json
{"versions": [{"version": "v1", "createdAt": "<ISO8601 UTC>"}, ...], "current": "v2"}
```

Before any commit `versions` is `[]` and `current` is `null`.

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

## Via the Go proxy

The Go server (default `:8090`) exposes the same endpoints under `/api/v1/models/{id}/edit/...`, one-to-one:

| Go proxy endpoint | Python endpoint |
| --- | --- |
| `PUT /api/v1/models/{id}/edit/entities/{guid}` | `PUT /models/{id}/entities/{guid}` |
| `GET /api/v1/models/{id}/edit/pending` | `GET /models/{id}/pending` |
| `DELETE /api/v1/models/{id}/edit/pending` | `DELETE /models/{id}/pending` |
| `GET /api/v1/models/{id}/edit/history` | `GET /models/{id}/history` |
| `GET /api/v1/models/{id}/edit/versions` | `GET /models/{id}/versions` |
| `POST /api/v1/models/{id}/edit/diff` | `POST /models/{id}/diff` |
| `POST /api/v1/models/{id}/edit/commit` | `POST /models/{id}/commit` |

Differences from direct access:

- Responses are wrapped in `{code, message, data}`; error mapping: 404 → 40400, 409 → 40900, 422 → 40001, anything else (including unreachable) → 50200.
- If a PUT/commit body contains `provenance.source`, Go validates the enum (UI|AI) first; invalid → 40001.
- After a Go-proxied commit: entries are expanded into the change log, `diff` is filled by IfcDiff, the model goes `converting` and reconversion is queued; the response data additionally contains `"reconverting": true`.
- A change-log write failure does not return 500: it is logged, the response stays 200 with a `"warning"` string (the IFC is persisted and reconversion is queued; only the change log may be missing entries).
