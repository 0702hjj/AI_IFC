# Design JSON editing & version diff (designer assist)

A "designer assist" editing/version model: **the design JSON is the single source of truth**; IFC is a derived artifact. Edits land on the design JSON (semantic parameter layer). No per-step history — diffs are computed only **between big versions**, and they are deliberately lightweight.

## Three core concepts

### 1. Design JSON (the edit surface)

`design JSON` expresses design intent (wall axes / along-axis openings / thickness / storey heights) — never coordinate math. The frontend locates a selected component's design entry via `Pset_AIIFC.designKey`, edits parameters, then regenerates the IFC.

Every element carries a stable `key` (e.g. `"1F:wall:0"`):

- The key never changes across edits → cross-version diff stays aligned.
- At build time it derives a **deterministic GlobalId** (`uuid5(NAMESPACE, key)`, identical across runs) and is written back to `Pset_AIIFC.designKey`.

### 2. Staging (WPS-style, up to 10 steps)

Edits go into an in-memory staging buffer (up to 10 states) with `<-` / `->` navigation:

- **Not saved** → discarding is lossless: **zero diff, zero version**.
- **Saved** → the staging chain is dropped and a **big version** is created.

```
edit staging (10 steps, in-memory, undo/redo)
   ├─ discard → dropped (no trace)
   └─ save → big version v{n} (designs/v{n}.json + versions/v{n}.ifc)
             └─ one diff between v{n-1} and v{n} only
```

### 3. Big versions & diff

- **Big version** = an explicit save point (AI auto-saves one on first generation; the designer saves subsequent ones).
- Paired snapshots: `models/{id}/designs/v{n}.json` + `models/{id}/versions/v{n}.ifc`.
- **Rollback** = restore a design JSON version, then regenerate the IFC (never per-step, never copying IFC).
- Diff is computed only between two big versions — lightweight, stateless, independent.

## Diff engine (between two big versions)

Primary path — **design JSON semantic diff** (covers models with provenance):

```json
{
  "base": "v1", "target": "v2", "engine": "design-json",
  "changed": [
    {"key": "1F:wall:0", "type": "IfcWall", "human_label": "1F wall 1 seg @ [0,0]→[14,0]",
     "changes": [{"field": "t", "old": 0.2, "new": 0.3}, {"field": "axis[1]", "old": [12,0], "new": [14,0]}]},
    {"key": "1F:wall:1", "type": "IfcWall", "human_label": "1F wall 1 seg @ [0,8]→[12,8]", "action": "removed"},
    {"key": "1F:opening:1", "type": "IfcDoor", "human_label": "1F door w=1.0m", "action": "added"}
  ]
}
```

Fallback path — **IFC semantic fingerprint diff** (covers externally uploaded / non-design models): compares element fingerprints (type / name / psets, keyed by designKey or GlobalId), no raw STEP parsing.

## API

All proxied through the Go server (`/api/v1`):

| Endpoint | Meaning |
|---|---|
| `GET /api/v1/models/{id}/design` | current design JSON (staged or last saved) |
| `PUT /api/v1/models/{id}/design` | stage one design JSON edit |
| `POST /api/v1/models/{id}/design/undo\|redo\|discard` | staging navigation / discard |
| `POST /api/v1/models/{id}/design/regenerate` | regenerate IFC from staged design (design_builder → build_script) |
| `POST /api/v1/models/{id}/design/save` | promote staged design to a big version (paired snapshot) |
| `GET /api/v1/models/{id}/designs` | list big versions |
| `POST /api/v1/models/{id}/design/rollback` | restore a design JSON version |
| `POST /api/v1/models/{id}/design/diff` | design JSON semantic diff (primary) |
| `POST /api/v1/models/{id}/design/diff-ifc` | IFC fingerprint diff (fallback) |

Frontend: select a component in the viewer → Design panel param form → stage / undo / redo / discard → regenerate + save big version; the version-compare panel shows the semantic diff between two big versions.

## Relationship to legacy IFC editing

- Models generated from design JSON: edit / version / diff go through this model.
- Externally uploaded IFC (no design JSON): diff degrades to IFC fingerprint; attribute overrides remain available (see [IFC property editing](/en/viewer/editing)).
