# IFC Property Editing

The property panel edits **the real IFC** on save (pending → commit, two phases). The property-override bypass has left the editing path and only remains as read-only display of historical data.

## True-edit property panel

Selecting an element renders a typed form driven by `GET /api/v1/models/{id}/edit/entities/{guid}/editable-schema`:

- **Direct attributes**: text inputs for strings, number inputs for int/float, checkboxes for bool, dropdowns of legal values for enums (e.g. `PredefinedType`) — enum lists come from the ifcopenshell schema declarations; illegal enum values are rejected server-side with 422 without damaging the model.
- **Pset properties**: scalar str/int/float/bool properties are editable with matching types; non-scalar properties stay out of the form.
- Saving issues `PUT /api/v1/models/{id}/edit/entities/{guid}` (pending; nothing on disk) and the panel shows an "uncommitted changes" hint; clicking **Commit** runs the commit orchestration (version snapshot + change log + diff + XKT reconversion), after which the frontend reloads automatically.
- **Delete element**: button + confirmation → `DELETE /api/v1/models/{id}/edit/entities/{guid}` enters pending (openings/fills, spatial containment, type associations and psets cascade-cleaned), takes effect on commit and is reflected in the version snapshot. IfcProject and spatial structure elements (site/building/storey/space) are refused (422).
- When the edit service is unavailable the panel degrades to read-only mode; historical overrides remain visible as read-only markers, and new edits no longer produce overrides.

## Migrating overrides to real edits

Legacy overrides can be replayed as real IFC modifications via `POST /api/v1/models/{id}/overrides/migrate`:

- Each entity is first PUT as pending, then committed in one go (`operation=migrate`), producing a new version snapshot.
- Successful fields have their overrides cleared; failed fields keep the override, with the reason returned in the response `failed`.
- Any success triggers XKT reconversion.

## Real-edit flow (pending → commit)

A real edit is a two-phase transaction:

1. **PUT pending**: applies `fields` (direct attributes) and `psets` (property sets, created when missing) to the in-memory model and records them as pending; **nothing is written to disk**. Full validation (including enum legality) runs before application — any validation failure means zero side effects.
2. **POST commit**: atomically persists all pending changes (tmp + rename, holding a per-model lock) → generates a version snapshot → appends the edit history → clears pending.

On a commit via the browser (Go proxy), the Go server additionally: expands the entries into the change log, fills diff fields with IfcDiff, marks the model `converting` and queues XKT reconversion — the frontend reloads automatically when it finishes.

Key points:

- Pending is persisted atomically on every change (`models/{id}/pending.json`) and restored automatically when the edit-service restarts; history and version snapshots are unaffected.
- A repeated commit (no pending) returns 409.
- Concurrent requests are serialized by one lock per model.

For the endpoint contract see [IFC Editing API](/en/reference/edit-api).
