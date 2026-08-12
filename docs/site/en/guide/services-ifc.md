# services/ifc: standalone deployment & calling

> Reusability promise: `services/ifc/` is the IFC business core (diff + script-as-source editing API). It runs **without Go server / web / converter / PostgreSQL** and can be moved to a new host as-is. It pairs with the `skills/aiifc/` skill — the skill produces build scripts, this service handles sandboxed execution, version snapshots and semantic diff.

## What it is

- **Standalone process**: FastAPI (Python 3.10+ + ifcopenshell + ifcdiff), default `:8100`.
- **Two core capabilities**:
  1. **script-as-source editing API** — all edits land on a build script (`PUT /script` stage → `script/run` sandbox preview → `script/save` big version); the IFC is just a build artifact.
  2. **diff** — GlobalId-keyed, field-level semantic diff between versions / against current state (`POST /diff`, `POST /diff/upload`); geometric noise is filtered out.
- **History**: formerly the viewer/edit-service business core, physically reorganized into `services/ifc/`; the retired L1 direct-edit chain (pending → commit) now answers 410.

## Standalone deployment

Prereq: Python 3.10+ and [uv](https://docs.astral.sh/uv/). Dependencies (`ifcopenshell` / `ifcdiff`) are official PyPI releases (IfcOpenShell 0.8.5); `uv sync` installs them — **no local source checkouts needed**.

```bash
cd services/ifc
uv sync
VIEWER_DATA_DIR="$(cd ../data && pwd)" uv run uvicorn app.main:app --port 8100
```

Self-hosted Swagger UI at `http://127.0.0.1:8100/docs` and raw schema at `/openapi.json`; `GET /health` returns `{"status": "ok"}`.

### Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `VIEWER_DATA_DIR` | `../data` | Model data root. **Use an absolute path**; the default is resolved against the process CWD (the top-level `data/` when started from `services/ifc/`). Same semantics as the Go `dataDir` |
| `AIIFC_FLOWS_DIR` | `../../skills/aiifc/references/docs/flows` | aiifc skill flows dir (the sandbox needs its `script_lib.py` for contract validation). Relative paths resolve against the `services/ifc/` root (CWD-independent) |
| `EDIT_SERVICE_PORT` | `8100` | Listen port |
| `EDIT_SERVICE_MAX_MODELS` | `8` | In-memory model cache (LRU) limit |

### Model file layout

Model ids must match `^m_[0-9a-f]{16}$`, mapped to `uploads/{id}.ifc`:

```
{VIEWER_DATA_DIR}/
├── uploads/
│   └── m_<16hex>.ifc            # current model state (atomically replaced by script/run or save)
└── models/
    └── m_<16hex>/
        ├── bootstrap.ifc        # original upload preserved on first staging (§5.4)
        ├── current.map.json     # ScriptMap envelope {"scriptHash", "map"} (published on run)
        ├── scripts/
        │   ├── v1.py            # big-version scripts (all kept, lockstep numbers)
        │   ├── v1.map.json
        │   └── v1.meta.json
        ├── versions/
        │   └── v1.ifc           # only the latest is materialized; history rebuilt from script on demand
        └── edit-history.json    # edit history (appended by user-edits, atomic write)
```

### Docker single-container deployment

The repo ships `services/ifc/Dockerfile` (Python 3.10 + uv + ifcopenshell, bubblewrap sandbox included). **The build context must be the repo root** — the image COPYs `skills/aiifc/references/docs/flows` (required by sandbox contract validation):

```bash
# run from the repo root
docker build -f services/ifc/Dockerfile -t aiifc-edit-service .

# run: mount the data volume + map the port (same semantics as VIEWER_DATA_DIR)
mkdir -p /srv/aiifc-data
docker run -d --name edit-service -p 127.0.0.1:8100:8100 -v /srv/aiifc-data:/data aiifc-edit-service
```

`VIEWER_DATA_DIR=/data`, `AIIFC_FLOWS_DIR=/opt/aiifc/flows` and `:8100` are baked into the image — no extra env needed. Smoke check: `curl -sf http://127.0.0.1:8100/openapi.json` returns 200, `GET /health` returns `{"status": "ok"}`.

Relationship to the full platform: **this container is only the business core**. The complete public chain (envelope wrapping, auth, upload → convert → browse) still needs the Go server + converter; an AI agent may also call the editing API directly on :8100 (pass `provenance.source="AI"`). Direct access has no auth — bind the port to 127.0.0.1 or keep it on an internal network; never expose it publicly.

## Callable endpoint catalog

Errors are FastAPI-shaped `{"detail": ...}`; **direct calls have no `{code, message, data}` envelope** — that is added by the Go server proxy (`code=0` on success, see [IFC Editing API](/en/reference/edit-api)). Machine-readable schema: [Editing API Reference (generated)](/reference/edit-api-reference) (Chinese).

### script-as-source editing (`app/routes_scripts.py`)

| Endpoint | Meaning |
| --- | --- |
| `GET /models/{id}/script` | current script (staged state or last saved big version) |
| `PUT /models/{id}/script` | stage one edit: exactly one of `{"script": ...}` (full replace) or `{"params": {...}}` (PARAMS-block rewrite) |
| `GET /models/{id}/script/params` | ast-extracted PARAMS (no execution) |
| `POST /models/{id}/script/undo` · `redo` · `discard` | staging navigation (10 steps) / discard |
| `POST /models/{id}/script/run` | sandbox-run staged script into uploads (preview, no version) |
| `POST /models/{id}/script/save` | promote to big version: run + lockstep snapshots `scripts/v{n}.py` + `v{n}.map.json` + `versions/v{n}.ifc` |
| `GET /models/{id}/scripts` | list big versions (scripts + versions) |
| `POST /models/{id}/script/rollback` | restore a big version's script into staging and re-run into uploads |
| `POST /models/{id}/script/diff` | script diff between two big versions (text diff + PARAMS changes + stats) |
| `GET /models/{id}/script/staging/diff?from=&to=` | small diff between two staging steps (default: last two) |
| `GET /models/{id}/script/locate?guid=` | guid → designKey → callsite (line/col/snippet/origin); miss → 200 `{"found": false}` |
| `POST /models/{id}/script/edit-call` | libcst scalar-argument rewrite + sandbox validation + stage in one step; **direct-only, not proxied via Go** |

### diff & versions (`app/routes_diff.py`)

| Endpoint | Meaning |
| --- | --- |
| `GET /models/{id}/versions` | version list + current version |
| `POST /models/{id}/diff` | body `{"base": "v1", "target": "v2"}` (target may be `"current"`); GlobalId-keyed `added/removed/changed` field-level semantic diff |

### read-only pending / history & user-edits (`routes_edits.py` / `routes_user_edits.py`)

| Endpoint | Meaning |
| --- | --- |
| `GET /models/{id}/pending` | current pending (script-run replay bookkeeping only since direct edits retired) |
| `DELETE /models/{id}/pending` | discard pending |
| `GET /models/{id}/history` | persisted edit history (read-only; new records come from `user-edits`) |
| `POST /models/{id}/user-edits` | record external user edits (`origin: "ifc-upload"|"dxf-upload"`) into history, stamped `source="USER"` |
| `POST /models/{id}/diff/upload` | multipart upload of a user-modified IFC vs current state (not persisted, not cached); adds a `labels` map |

### Retired endpoints (410 Gone)

`PUT/DELETE /models/{id}/entities/{guid}`、`GET .../editable-schema`、`POST /models/{id}/commit` answer 410 — direct IFC editing is retired; all edits go through the build script (recovery anchor `fb55a8a`).

## Optionality boundary

Everything outside services/ifc is **optional**:

| Component | Without it, services/ifc still… | You lose |
| --- | --- | --- |
| **Go server** (:8090) | serves the full edit/diff/version REST surface directly (:8100) | `{code,message,data}` envelope, `/api/v1` public entry, auth (`Authorization: Bearer`), XKT reconversion orchestration after run/save, browser session bridging |
| **web** (React) | API-only usage works unchanged | visualization (xeokit 3D), model tree / property panel / script editor / Diff Viewer |
| **converter** (Node) | editing and diff fully work | IFC → XKT rendering conversion (needed for web visualization) |
| **PostgreSQL** | editing and diff fully work (file storage default) | PG persistence of issues / changes / overrides (optional storage abstraction) |

Model upload (`uploads/{id}.ifc`) and the `data/` layout are the only data contract — any component that writes `uploads/{id}.ifc` under the same `VIEWER_DATA_DIR` can feed the edit service.

## Porting guide

Minimal steps to move to a new host:

1. Copy `services/ifc/` and `skills/aiifc/` (the sandbox needs `script_lib.py` from its flows).
2. `cd services/ifc && uv sync` (PyPI deps, no local IfcOpenShell source).
3. Point `VIEWER_DATA_DIR` (absolute path) at your model data root; set `AIIFC_FLOWS_DIR` if needed.
4. `uv run uvicorn app.main:app --port 8100`; verify via Swagger UI.

Skill contract: see aiifc SKILL.md **MUST #25-31** — top-level `PARAMS` literal dict, elements created via `script_lib.create_entity` (deterministic GlobalId + `Pset_AIIFC.designKey` + callsite record), `build(params, out_path)` entry, output validated through `script_lib.write_and_validate` (`ifcopenshell.validate`). The server-side static contract check and sandbox (`app/script_runner.py`) depend only on the flows dir. Full integration (dual-role architecture, curl walkthrough, provenance model): [AI Integration](/en/reference/ai).

## Honest boundaries

- **No auth**: direct :8100 has no token check — keep it on 127.0.0.1, never expose publicly. Go server for public-facing auth.
- **provenance is a declared field**: `provenance.source` (AI/UI/USER) is self-reported by the caller; only enum-validated, not identity-verified.
- **Sandbox dependencies**: run/save need ifcopenshell + aiifc flows (`script_lib` contract check); without bwrap the sandbox degrades to rlimit (FS writes outside the sandbox and network are not blocked — rely on container isolation).
- **Cache semantics**: in-memory model cache is bounded (`EDIT_SERVICE_MAX_MODELS`); staging is memory-only (unrun staging is lost on restart), big versions are persisted on disk.
