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
- Entry point `build(params: dict, out_path: str)`; the output must pass `ifcopenshell.validate`.

### 2. Staging (WPS-style, up to 10 steps)

Script edits (full replace or PARAMS-only rewrite) go into a staging buffer (up to 10 steps, persisted atomically and restored after a restart) with undo / redo:

- **Discard** → the staging chain is dropped: **zero diff, zero version**.
- **Run** → the staged script executes in the sandbox for a preview, without creating a version.
- **Save** → the script runs, and script + IFC are snapshotted together as a **big version**.

```
script staging (10 steps, persisted, undo/redo)
   ├─ discard → dropped (no trace)
   ├─ run → sandboxed preview into uploads (no version)
   └─ save → big version v{n} (scripts/v{n}.py + versions/v{n}.ifc)
```

### 3. Big versions & rollback

- **Big version** = an explicit save point, snapshotted as a pair: `models/{id}/scripts/v{n}.py` + `models/{id}/versions/v{n}.ifc`.
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
| `PUT /api/v1/models/{id}/script` | stage a script edit (full replace or PARAMS-only) |
| `GET /api/v1/models/{id}/script/params` | the current script's PARAMS dict (AST extraction, no execution) |
| `POST /api/v1/models/{id}/script/undo\|redo\|discard` | staging navigation / discard |
| `POST /api/v1/models/{id}/script/run` | sandbox-run the staged script (preview, no version) |
| `POST /api/v1/models/{id}/script/save` | promote the staged script to a big version (run + paired snapshot) |
| `GET /api/v1/models/{id}/scripts` | list big versions |
| `POST /api/v1/models/{id}/script/rollback` | restore a script version and re-run it |
| `POST /api/v1/models/{id}/script/diff` | script diff between two big versions (text + PARAMS changes) |
| `GET /api/v1/models/{id}/script/staging/diff` | small-version diff between staging steps |

## Relationship to IFC attribute editing

- Script-generated models: edit / version / diff go through this model; fine-grained attribute edits remain available via [IFC attribute editing](/en/viewer/editing) (pending → commit).
- Externally uploaded IFC (no script): no script diff; version compare uses attribute-level semantic diff (by GlobalId).
