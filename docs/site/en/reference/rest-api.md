# Viewer REST API

Backend base: `http://localhost:8090`; every JSON response uses the envelope `{code, message, data}` with `code=0` meaning success. Model ids look like `m_` + 16 lowercase hex characters.

## Models

### POST /api/v1/models

Upload an IFC file and trigger asynchronous conversion. Request: `multipart/form-data`, field `file` (only `.ifc`, ≤200MB).

Response:

```json
{"code":0,"message":"ok","data":{"id":"m_01J...","name":"Building-Architecture.ifc","status":"converting"}}
```

Errors: `40001` invalid file type; `40002` over the size limit.

### GET /api/v1/models

Model list (the frontend polls every 2s until all models leave `converting`):

```json
{"code":0,"message":"ok","data":[
  {"id":"m_01J...","name":"a.ifc","size":1832140,"status":"ready","createdAt":"2026-07-27T10:00:00Z","error":""}
]}
```

`status` ∈ `converting | ready | failed`.

### GET /api/v1/models/{id} {#model-detail}

Single-model detail, same shape.

### POST /api/v1/models/{id}/retry

Re-enqueue conversion for a `failed` model; returns the updated model object (`status:"converting"`).

### DELETE /api/v1/models/{id} {#delete-model}

Deletes the model's IFC, XKT, metadata, state file and issues/changes/overrides. Response `data: null`.

### GET /api/v1/models/{id}/download

Download the original IFC with `Content-Disposition: attachment; filename="<name>"`.

## Issues

Issue ids look like `i_` + 12 lowercase hex; `status` ∈ `open | checking | resolved`; `author` defaults to `local-user`; `provenance.source` defaults to `UI` (can be overridden at creation).

### GET /api/v1/models/{id}/issues

Returns `data: Issue[]` ordered by createdAt descending.

### POST /api/v1/models/{id}/issues

`multipart/form-data`:

- `issue` (required): JSON string `{"entityId","entityName","entityType","title","comment","author"?,"provenance"?,"camera":{"eye":[...],"look":[...],"up":[...]}}`; `title` is required.
- `screenshot` (optional): PNG file, ≤5MB.

Returns `data: Issue` (with the generated id, `status:"open"`, default author/provenance, `screenshot` relative path, createdAt/updatedAt).

### PATCH /api/v1/models/{id}/issues/{issueId} {#patch-issue}

JSON body: `{"title"?, "comment"?, "status"?}` — only the given fields are updated.

### DELETE /api/v1/models/{id}/issues/{issueId} {#delete-issue}

Deletes the issue and its screenshot.

### GET /v1/models/{id}/issues/{file}

Issue screenshot static service; `file` must match `i_[0-9a-f]{12}\.png`.

## Property overrides and change log

Property edits go through metadata overrides (the IFC itself is untouched): whitelisted fields are exactly `Name / Description / Classification / FireRating / Comments`; every change writes one change log entry per field.

### GET /api/v1/models/{id}/overrides

Returns `data: { [entityId]: { [field]: value } }` (`{}` when empty).

### PUT /api/v1/models/{id}/entities/{entityId}/properties

JSON body: `{"entityName":"Wall","fields":{"FireRating":"F60","Comments":"note"}}`.

- `fields` is required and non-empty; a name outside the whitelist returns `40001 field not in whitelist`.
- An empty string clears that field's override.
- Every field writes a change log entry (oldValue is the previously effective value; author `local-user`; provenance `UI`).
- Returns `data: { [field]: value }`, the entity's current effective overrides.

### GET /api/v1/models/{id}/changes

Returns `data: ChangeEntry[]` ordered by createdAt descending (`[]` when empty):

```json
{"code":0,"message":"ok","data":[
  {"id":"c_1a2b3c4d5e6f","entityId":"3a82-xxxx","entityName":"Wall","field":"FireRating","oldValue":"","newValue":"F60","author":"local-user","provenance":{"source":"UI"},"operation":"update","createdAt":"2026-07-29T10:00:00Z"}
]}
```

## Edit proxy endpoints

The Go server proxies the edit-service script-editing endpoints under `/api/v1/models/{id}/script/...` (orchestration: after run/save/rollback it queues XKT reconversion); read-only/compare endpoints stay under `/api/v1/models/{id}/edit/...` (`edit/diff`, `edit/pending`, `edit/history`, `edit/versions`). The direct-edit proxy routes (`edit/entities/{guid}`, `edit/commit`) were removed with the L1 direct-edit retirement. Full contract: [IFC Editing API](/en/reference/edit-api).

## Static resources (no envelope)

| Path | Description |
| --- | --- |
| `GET /v1/models/{id}/model.xkt` | XKT geometry (supports Range) |
| `GET /v1/models/{id}/metadata.json` | metadata (below) |
| `GET /v1/models/{id}/render.json` | CAD render payload (kind=dxf models only, below) |
| `GET /v1/models/{id}/issues/{file}` | issue screenshots |

## metadata.json Schema (xeokit meta-model format)

Extracted from the original IFC by the converter (spatial tree + property sets), directly usable as `XKTLoaderPlugin.load({metaModelSrc})`:

```json
{
  "projectId": "3xFoo",
  "metaObjects": [
    {"id": "1AbC...", "type": "IfcBuildingStorey", "name": "Level 1", "parent": "0Root"},
    {"id": "2XdE...", "type": "IfcWall", "name": "Wall-001", "parent": "1AbC...", "propertySetIds": ["pset_2XdE_0"]}
  ],
  "propertySets": [
    {
      "id": "pset_2XdE_0",
      "name": "Pset_WallCommon",
      "type": "Pset",
      "properties": [
        {"name": "FireRating", "value": "120min", "type": "IfcLabel"},
        {"name": "LoadBearing", "value": true, "type": "IfcBoolean"}
      ]
    }
  ]
}
```

Conventions: `metaObjects[].id` is the IFC GlobalId (identical to the XKT entity id); hierarchy is Site → Building → Storey → element; elements without psets omit `propertySetIds`.

## render.json Schema (render payload v2)

Atomically published by services/cad after `script/run` and `script/save` succeed (the file exists only for kind=dxf models); serves the frontend Canvas 2D read-only preview. Coordinates keep the original DXF coordinate system (no normalization):

```json
{
  "schemaVersion": 2,
  "bounds": {"min": [0, 0], "max": [100, 80]},
  "layers": [{"name": "WALL", "color": 7, "linetype": "CONTINUOUS"}],
  "entities": [
    {"key": "e_1a2b3c", "type": "LINE", "layer": "WALL", "start": [0, 0], "end": [10, 0]}
  ],
  "unsupported": [{"type": "HATCH", "handle": "1F", "coords": [5, 5]}]
}
```

Conventions: `entities[].key` is the stable XDATA key (APPID `AIDXF`, same source as the ScriptMap), so the frontend gets the key on selection; LWPOLYLINE is exploded into LINE/ARC entries (multiple entries share one key); INSERT is expanded one level only (child entities have `key=null` and a `block` marker); entity types outside the whitelist are listed in `unsupported` instead of being silently dropped.

## Common error codes

`40001` parameter/validation error, `40002` over limit, `40400` model or issue not found, `50000` internal server error.
