# Architecture

```mermaid
graph LR
  subgraph Clients
    UI[Browser<br/>React 19 + xeokit<br/>viewer/web]
    AI[AI Agent]
  end

  subgraph Services
    GO[Go server :8090<br/>viewer/server<br/>orchestration / REST / storage abstraction]
    PY[Python edit-service :8100<br/>viewer/edit-service<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>viewer/converter<br/>IFC → XKT + metadata.json]
  end

  subgraph Storage
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(Filesystem<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|same editing API| PY
  AI -->|or via Go proxy| GO
  GO -->|/api/v1/models/{id}/edit/* proxy + orchestration| PY
  GO -->|subprocess node convert.js| CV
  GO -->|pgx/v5, optional| PG
  GO --> FS
  PY -->|real IFC edits / version snapshots / history| FS
  CV -->|model.xkt + metadata.json| FS
```

## Component responsibilities

| Component | Tech | Responsibility | Why this tech |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | all review/edit/diff interaction | xeokit's XKT binary loading and BIM toolchain |
| server | Go 1.26 (stdlib net/http + pgx/v5) | upload/conversion queue, REST, edit orchestration, storage abstraction | static binary, concurrency model |
| converter | Node CLI (web-ifc + xeokit-convert) | IFC → XKT geometry + semantic extraction | xeokit-convert only ships as npm |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | real IFC edits, pending/commit, version snapshots, semantic diff | IfcOpenShell is the de-facto standard for IFC editing |
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

### Edit flow

```
PUT /models/{id}/entities/{guid}  {fields, psets, author, provenance}
  → full validation (any failure → 422, zero side effects) → apply to the in-memory model → record pending (with the real IFC oldValue)
POST /models/{id}/commit
  → atomic write (tmp+rename, per-model lock) → version snapshot versions/v{n+1}.ifc → append edit-history.json → clear pending
(via the Go proxy, orchestration continues:)
  → change log expanded per field (operation=update, diff filled by IfcDiff, non-fatal)
  → conversion queue reconverts XKT → frontend polls until ready and auto-reloads
```

### Versions and diff

- Before the first commit the original upload is copied to `versions/v1.ifc`; every commit snapshots `v{n+1}.ifc` (append-only).
- `POST /models/{id}/diff {base, target}`: IfcDiff (`relationships=["attributes","property"]`, geometry excluded by construction) yields added/removed sets; the adapter computes field-level old/new for changed entities; the result reduces to `{added, removed, changed:[{guid, changes:[{field,old,new}]}]}`.
- Snapshot-to-snapshot diff results are cached (versions are immutable, so the cache is naturally valid).

### Override → real-edit migration

```
Read all overrides → map per entity (Name/Description/Comments → fields;
  FireRating → look up the pset in metadata.json; Classification → try fields, 422 goes to failed)
→ one PUT (pending) per entity → one commit (operation=migrate)
→ successful fields clear their override; change log carries real old values; failed fields keep overrides with reasons
→ any success triggers reconversion
```

## Commit / version model

Change log entries carry: `author` (default `local-user`, no auth in v1), `createdAt` (UTC), `operation` (`update | migrate`), `diff` (filled by IfcDiff at commit), `provenance` (`{source: UI|AI}`, validated at the API layer). Versions form a linear snapshot sequence (branching/merging is out of scope, belongs to multi-user).

Known technical debt (details in [Known limitations](/project/known-limits), Chinese): three history records coexist (Go change log / edit-service edit-history / pending) with different granularity and purposes; diff has no timeout; the Python side is file-storage only.
