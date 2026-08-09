# Script-as-source: script editing & version diff (designer assist)

A "designer assist" editing/version model: **the Python build script is the only one-to-one representation of the IFC model (script-as-source)**; the IFC file is a derived artifact produced by sandboxed script execution. Edits land on the script (PARAMS or the script body). No per-step history — diffs are computed between big versions and between staging steps, and they are deliberately lightweight.

## Boundary: where design JSON fits

**Design JSON is an auxiliary draft from the AI drafting stage** — it is NOT a complete representation of the model, NOT an annotation file for the IFC, NOT versioned, and NOT diffed. **The only artifact that corresponds one-to-one with the IFC is the build script**: `scripts/v{n}.py` → (sandboxed run) → `versions/v{n}.ifc`. The AI may produce a design JSON draft to organize its thinking for complex models (see the [aiifc skill](/en/reference/ai-skill)), but the deliverable is always the script.

## Workflow: plan draft → script → IFC

```
plan / design draft (optional, AI thinking aid, never versioned)
   → build script v{n}.py (single source of truth: PARAMS + build())
   → sandboxed execution → IFC v{n} (derived artifact, rebuildable from the script)
```

## Three core concepts

### 1. The build script (the edit surface)

Every AI-generated model corresponds to a complete Python build script following the script contract:

- A top-level literal `PARAMS = {...}` dict (JSON-compatible) holding every tunable parameter.
- Deterministic identity: each element's GlobalId derives from `uuid5(NAMESPACE_AI_IFC, key)` and is written to `Pset_AIIFC.designKey` — same script + same PARAMS → identical GlobalIds across runs, so cross-version diffs stay aligned.
- **C-locate (contract #30)**: review-visible elements MUST be created via the contract factory `script_lib.create_entity(...)` — the factory derives the deterministic GlobalId, writes `Pset_AIIFC.designKey` and records the callsite (line/col/snippet/origin) at run time; bypassing it with raw `root.create_entity` is forbidden.
- **C-scalar (contract #31)**: parameters meant to be web-editable MUST be scalar literals or PARAMS references, never arbitrary expressions (edit-call refuses them; fall back to editing the script).
- Entry point `build(params: dict, out_path: str)`; the output must pass `ifcopenshell.validate`.

### 2. Staging (WPS-style, up to 10 steps)

Script edits (full replace or PARAMS-only rewrite) go into a staging buffer (up to 10 steps, persisted atomically and restored after a restart) with undo / redo:

- **Discard** → the staging chain is dropped: **zero diff, zero version**.
- **Run** → the staged script executes in the sandbox for a preview, without creating a version.
- **Save** → the script runs, and script + ScriptMap are snapshotted together as a **big version** (only the latest IFC stays materialized).

```
script staging (10 steps, persisted, undo/redo)
   ├─ discard → dropped (no trace)
   ├─ run → sandboxed preview into uploads (no version)
   └─ save → big version v{n} (scripts/v{n}.py + v{n}.map.json; versions/v{n}.ifc only for the latest)
```

### 3. Big versions & rollback

- **Big version** = an explicit save point: `models/{id}/scripts/v{n}.py` + `v{n}.map.json` (+ `v{n}.meta.json`) are kept in full, numbered in lockstep.
- **Only the latest IFC is materialized**: `versions/v{n}.ifc` keeps the newest big version; historical IFCs are rebuilt on demand from their scripts (sandbox re-run, cached in `ifc_cache/` with LRU capacity 4). Rebuilds are only semantically equal to the original snapshots (deterministic GlobalIds; header timestamps differ) — always compare via semantic diff.
- **Rollback** = restore a script version, then re-run it to rebuild the IFC (script and IFC can never diverge).
- The next AI iteration receives: current script + script diff + IFC semantic diff summary → incremental edits instead of rewrites.

## Diff engine (three layers × two granularities)

Two granularities: **big versions** (v{n-1} ↔ v{n}) and **small versions** (between staging steps, lightweight inline diff). Both are visible to the AI and the user.

| Layer | Object | Audience |
|---|---|---|
| Script unified text diff + PARAMS key-level changes | `scripts/v{n-1}.py` ↔ `v{n}.py`; between staging steps | AI (context for the next output) + user (script diff view) |
| IFC semantic diff (ifcdiff, attribute-level, GlobalId-aligned) | `versions/v{n-1}.ifc` ↔ `v{n}.ifc` | User (Diff Viewer, see [version diff](/en/viewer/versions-diff)) |
| Externally uploaded models | attribute-level semantic diff (by GlobalId) when no script exists | User |

## PARAMS form & script editor (frontend)

The Design panel parses the current script's `PARAMS` block to generate a parameter form automatically (AST extraction, no execution); drilling down opens the script editor for direct edits. Form submit / script save = one staging step; "save version" = run the script → big version. The compare panel shows script diff and IFC semantic diff between two big versions, or small-version diffs between adjacent staging steps.

## Execution safety

The edit-service runs scripts in a subprocess with a 60s timeout, rlimits (CPU/memory) and an isolated temporary directory; failures return 422 with the last 2KB of stderr. Container deployments are naturally offline (compose internal network).

## API

All proxied through the Go server (`/api/v1`):

| Endpoint | Meaning |
|---|---|
| `GET /api/v1/models/{id}/script` | current script (staged state or last saved) |
| `PUT /api/v1/models/{id}/script` | stage a script edit (full replace or PARAMS-only); the first staging on a plain model preserves the original upload as `bootstrap.ifc` |
| `GET /api/v1/models/{id}/script/params` | the current script's PARAMS dict (AST extraction, no execution) |
| `POST /api/v1/models/{id}/script/undo\|redo\|discard` | staging navigation / discard |
| `POST /api/v1/models/{id}/script/run` | sandbox-run the staged script (preview, no version) |
| `POST /api/v1/models/{id}/script/save` | promote the staged script to a big version (run + script/map paired snapshot); when `bootstrap.ifc` exists the response carries an `alignment` count (added/removed/changed) |
| `GET /api/v1/models/{id}/scripts` | list big versions |
| `POST /api/v1/models/{id}/script/rollback` | restore a script version and re-run it |
| `POST /api/v1/models/{id}/script/diff` | script diff between two big versions (text + PARAMS changes) |
| `GET /api/v1/models/{id}/script/staging/diff` | small-version diff between staging steps |
| `GET /api/v1/models/{id}/script/locate?guid=` | guid → designKey → callsite (line/col/snippet/origin); miss → 200 `{"found": false}` |

Edit-service direct only (`:8100`, not proxied by the Go server):

| Endpoint | Meaning |
|---|---|
| `POST /models/{id}/script/edit-call` | libcst scalar-argument rewrite (body: `{designKey, argument, value}`) → sandbox validation → staged on success; `origin=traced` / non-scalar / illegal argument name / non-finite float → 422 with zero side effects |

## The locate chain (ScriptMap)

On every sandboxed `build()` run, the contract factory records each element's callsite and `write_and_validate` writes the map sidecar; save snapshots it in lockstep with the script as `scripts/v{n}.map.json`:

```python
ScriptMap = dict[designKey, {"line": int, "col": int, "snippet": str,
                             "origin": "literal" | "params" | "traced"}]
```

The map is strictly same-version with the script (regenerated whenever the script changes) — a "stale map" state does not exist. Locate queries the current map (staging first, then the latest big version); `origin` decides the web rewrite strategy (see [IFC script editing](/en/viewer/editing)).

## Bootstrap: uploaded IFC → script

A plain model becomes script-backed through AI reproduction: the AI reads the uploaded IFC via MCP → writes a reproduction script with the aiifc skill → `PUT /script` (the platform preserves the original upload as `bootstrap.ifc`) → sandbox validation → `script/save` stores v1. The save response's `alignment` count (attribute-level semantic diff summary of the bootstrap original vs the generated IFC) is the acceptance signal for reproduction fidelity; a failed alignment computation never fails the save itself (logged, returned as null).

## Relationship to the (retired) direct-edit chain

- Script-generated models: editing / versioning / diffing all go through this page's model (select → locate → rewrite → sandbox → staging → big version).
- Externally uploaded IFC (plain state): no editing entry — view/review only; version compare uses attribute-level semantic diff (by GlobalId).
- The former L1 direct-edit chain (`PUT/DELETE /models/{id}/entities/...`, `POST .../commit`) is **retired** and returns 410 Gone; `POST /models/{id}/diff` (IFC semantic diff) and `POST /models/{id}/diff/upload` are kept.
