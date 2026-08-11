# Architecture

```mermaid
graph LR
  subgraph Clients
    UI[Browser<br/>React 19 + xeokit<br/>web]
    AI[AI Agent]
  end

  subgraph Services
    GO[Go server :8090<br/>server<br/>orchestration / REST / storage abstraction]
    PY[Python edit-service :8100<br/>services/ifc<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>converter<br/>IFC → XKT + metadata.json]
  end

  subgraph Storage
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(Filesystem<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|same editing API| PY
  AI -->|or via Go proxy| GO
  GO -->|/api/v1/models/{id}/script/* proxy + orchestration| PY
  GO -->|subprocess node convert.js| CV
  GO -->|pgx/v5, optional| PG
  GO --> FS
  PY -->|script sandbox runs / version snapshots / history| FS
  CV -->|model.xkt + metadata.json| FS
```

## Component responsibilities

| Component | Tech | Responsibility | Why this tech |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | all review/edit/diff interaction | xeokit's XKT binary loading and BIM toolchain |
| server | Go 1.26 (stdlib net/http + pgx/v5) | upload/conversion queue, REST, edit orchestration, storage abstraction | static binary, concurrency model |
| converter | Node CLI (web-ifc + xeokit-convert) | IFC → XKT geometry + semantic extraction | xeokit-convert only ships as npm |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | script sandbox execution, version snapshots (script-as-source), ScriptMap locate, semantic diff | IfcOpenShell is the de-facto standard for IFC editing |
| PostgreSQL | optional | issues / changes / overrides tables | without `pgDSN` everything is file-based and dependency-free |

## Core data flows

### Upload and conversion

```
Browser upload .ifc → Go validates and stores uploads/{id}.ifc (status=converting)
  → conversion queue (2 workers, dedup + dirty rerun) → node convert.js
  → models/{id}/model.xkt (geometry) + metadata.json (spatial tree / psets)
  → status=ready → XKTLoaderPlugin loads geometry and semantics together
```

Key invariant: **XKT element id = metadata metaObject id = IFC GlobalId** — selection, highlighting and diff results all rely on this chain.

### Edit flow (script-as-source)

Every web/AI edit is an edit to the build script; the IFC is a derived artifact of sandboxed script execution. The former L1 direct-edit chain (`PUT /entities/{guid}` → pending → `POST /commit` mutating the IFC) is retired (410, recovery anchor `fb55a8a`).

```
PUT /models/{id}/script  {script | params}
  → static contract validation (422, zero side effects) → one staged step (10-step ring, persisted, undo/redo)
  (the first staging on a plain model preserves the original upload as bootstrap.ifc)
POST /models/{id}/script/run      sandboxed preview (no version)
POST /models/{id}/script/save
  → sandbox-run the script to produce the IFC (failure → 422, staging preserved)
  → big version v{n}: scripts/v{n}.py + v{n}.map.json paired snapshot (lockstep)
  → versions/v{n}.ifc materializes only the latest; older scripted snapshots are pruned (rebuildable on demand)
  → when bootstrap.ifc exists the response carries an alignment count
(via the Go proxy, after run/save/rollback:)
  → conversion queue reconverts XKT → frontend polls until ready and auto-reloads
```

Locate and targeted rewrite:

```
GET /models/{id}/script/locate?guid=
  → read Pset_AIIFC.designKey from the IFC → query the current ScriptMap (staging first)
  → hit: {line, col, snippet, origin}; miss: 200 {"found": false}
POST /models/{id}/script/edit-call  {designKey, argument, value}  (edit-service direct only)
  → libcst scalar rewrite → contract validation + sandbox re-run → staged on success; any failure 422, zero side effects
```

### Versions and diff

- Big versions are a lockstep trio: `scripts/v{n}.py` (source of truth) + `v{n}.map.json` (locate) kept in full; `versions/v{n}.ifc` materializes only the latest — historical IFCs are rebuilt from their scripts on demand (`ifc_cache/` LRU 4). Deterministic GlobalIds keep rebuilds semantically aligned; bytes are never asserted.
- `POST /models/{id}/diff {base, target}`: IfcDiff (`relationships=["attributes","property"]`, geometry excluded by construction) yields added/removed sets; the adapter computes field-level old/new for changed entities; the result reduces to `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`.
- Snapshot-to-snapshot diff results are cached (versions are immutable, so the cache is naturally valid); `POST /diff/upload` compares an externally edited IFC (nothing persisted or cached).

## Version model

Change log entries carry: `author` (default `local-user`, no auth in v1), `createdAt` (UTC), `operation`, `provenance` (`{source: UI|AI|USER}`, validated at the API layer). Versions form a linear snapshot sequence (branching/merging is out of scope, belongs to multi-user); rollback = restore a historical script and re-run it (append-only, history is never rewritten).

Known technical debt (details in [Known limitations](/project/known-limits), Chinese): multiple history records coexist (Go change log / edit-service edit-history) with different granularity and purposes; diff has no timeout; the Python side is file-storage only.
