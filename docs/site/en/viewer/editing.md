# IFC Property Editing

Property editing has two stages: **override (display layer) → real edit (written back to the IFC)**.

## Stage 1: property override

Whitelisted fields in the property panel are editable; the whitelist is exactly:

`Name`, `Description`, `Classification`, `FireRating`, `Comments`

- A saved edit is stored as an override over the displayed value **without modifying the IFC itself**; overridden fields carry a modification marker.
- An empty string clears that field's override.
- Each change writes one change-log entry per field (`operation=update`, `author=local-user`, `provenance={source:"UI"}`), viewable in the change history tab.
- Related API: `GET /api/v1/models/{id}/overrides`, `PUT /api/v1/models/{id}/entities/{entityId}/properties`, `GET /api/v1/models/{id}/changes`.

## Stage 2: migrating overrides to real edits

`POST /api/v1/models/{id}/overrides/migrate` replays all current overrides as real IFC modifications:

- Each entity is first PUT as pending, then committed in one go (`operation=migrate`), producing a new version snapshot.
- Successful fields have their overrides cleared; failed fields keep the override, with the reason returned in the response `failed`.
- Any success triggers XKT reconversion.

## Real-edit flow (pending → commit)

A real edit is a two-phase transaction:

1. **PUT pending**: applies `fields` (direct attributes) and `psets` (property sets, created when missing) to the in-memory model and records them as pending; **nothing is written to disk**. Full validation runs before application — any validation failure means zero side effects.
2. **POST commit**: atomically persists all pending changes (tmp + rename, holding a per-model lock) → generates a version snapshot → appends the edit history → clears pending.

On a commit via the browser (Go proxy), the Go server additionally: expands the entries into the change log, fills diff fields with IfcDiff, marks the model `converting` and queues XKT reconversion — the frontend reloads automatically when it finishes.

Key points:

- Pending is persisted atomically on every change (`models/{id}/pending.json`) and restored automatically when the edit-service restarts; history and version snapshots are unaffected.
- A repeated commit (no pending) returns 409.
- Concurrent requests are serialized by one lock per model.

For the endpoint contract see [IFC Editing API](/en/reference/edit-api).
