# AI Integration

An integration guide for AI agents: with script-as-source, AI edits land on the build script — stage (`PUT /script`) → sandbox run (`script/run`) → save a big version (`script/save`). The machine-consumable schema: [OpenAPI Files](/en/reference/openapi).

> **Direct editing retired**: the former "edit attribute → pending → commit" endpoints (`PUT /entities/{guid}`, `POST /commit`, …) return 410 Gone. Fine-grained parameter changes now use `POST /script/edit-call` (libcst scalar rewrite) or PARAMS staging.

## One API, two roles

Humans (browser) and AI agents use the **same script-editing endpoints**; only the entry point differs:

```
Browser (human) ──► Go server :8090 ──proxy──► Python edit-service :8100
                  /api/v1/models/{id}/script/...  │  /models/{id}/script/...
AI agent ────────► REST direct ──────────────────┘  (or via the Go proxy, one-to-one)
```

- Human: browser → Go proxy; after a successful run/save/rollback the Go side queues XKT reconversion.
- AI: REST directly to edit-service (default `http://127.0.0.1:8100`); the Go proxy works too. `script/edit-call` is **not** proxied — direct only.
- The Python service ships Swagger UI (`/docs`) and the raw schema (`/openapi.json`).

## Quick start

```bash
# 1) Python edit service (default port 8100)
cd services/ifc
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server (default 127.0.0.1:8090)
cd server
go run ./cmd/server
```

**dataDir consistency**: `VIEWER_DATA_DIR` must point to the same directory as the Go `server_config.json` `dataDir` (both locate model files at `{dataDir}/uploads/{id}.ifc`).

## Direct AI flow (curl)

Prerequisite: a model exists (id like `m_` + 16 lowercase hex) with its file at `{VIEWER_DATA_DIR}/uploads/{id}.ifc`.

### A. Bootstrap: reproduce an uploaded IFC as a script

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef

# 1. Write a reproduction script with the aiifc skill (the MCP server can read
#    the model) and stage it. The first staging preserves the original upload
#    as bootstrap.ifc.
curl -X PUT "$BASE/models/$MID/script" \
  -H 'Content-Type: application/json' \
  -d '{"script": "PARAMS = {...}\n\ndef build(params, out_path):\n    ...\n"}'

# 2. Sandbox trial run (preview, no version)
curl -X POST "$BASE/models/$MID/script/run"

# 3. Save big version v1 (script + map paired snapshot)
#    The response carries an alignment count: semantic-diff summary of the
#    bootstrap original vs the generated IFC.
curl -X POST "$BASE/models/$MID/script/save" \
  -H 'Content-Type: application/json' -d '{"note": "bootstrap v1"}'
```

### B. Targeted edits on an existing script

```bash
# 1. Locate the callsite by guid (line/col/snippet/origin)
curl "$BASE/models/$MID/script/locate?guid=2O2Fr\$t4X7ZfFPoeewFlqU"

# 2a. origin=params: change PARAMS keys only, one staged step
curl -X PUT "$BASE/models/$MID/script" \
  -H 'Content-Type: application/json' \
  -d '{"params": {"wall_height": 3.2}}'

# 2b. origin=literal: libcst scalar rewrite + sandbox validation + staging
curl -X POST "$BASE/models/$MID/script/edit-call" \
  -H 'Content-Type: application/json' \
  -d '{"designKey": "L1:wall:1", "argument": "height", "value": 3.2}'

# 3. Save a big version
curl -X POST "$BASE/models/$MID/script/save"

# 4. Compare versions: script diff + IFC semantic diff
curl -X POST "$BASE/models/$MID/script/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "v2"}'
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' -d '{"base": "v1", "target": "current"}'
```

> Direct run/save calls do **not** trigger Go-side XKT reconversion. For frontend-visible refreshes use the Go proxy: `http://127.0.0.1:8090/api/v1/models/$MID/script/...`.

## Contract highlights

- **Script contract** (aiifc skill MUST #25-31): top-level literal `PARAMS` dict; elements created via the `script_lib.create_entity` factory (deterministic GlobalId + `Pset_AIIFC.designKey` + callsite recording, C-locate #30); web-editable parameters are scalar literals or PARAMS references (C-scalar #31); `build(params, out_path)` entry; output passes `ifcopenshell.validate`.
- **Failure semantics**: contract-validation or sandbox build failure → 422 with zero side effects; edit-call refuses `origin=traced` / non-scalars / illegal argument names / non-finite floats with 422; locate miss → 200 `{"found": false}` (never 5xx).
- **Version semantics**: `scripts/v{n}.py` + `v{n}.map.json` kept in full, numbered in lockstep; `versions/v{n}.ifc` materializes only the latest — history is rebuilt on demand (aligned via semantic diff, never byte equality).
- **Provenance**: register external user modifications via `POST /models/{id}/user-edits` (`source="USER"`); issue creation still accepts `provenance.source`.

## Limits and roadmap

v1 limits (details in [Known limitations](/project/known-limits), Chinese): single-machine single-user, no auth (do not expose publicly); `VIEWER_DATA_DIR` must equal the Go `dataDir`; diff is attribute-level only.

## Division of labor with the aiifc skill

The REST editing API fits targeted edits on an existing script (staging / versioning / diffs). For **building models from scratch or large geometry changes**, use the [AI Skill (aiifc)](/en/reference/ai-skill) — the agent writes a contract-conforming `ifcopenshell.api` build script, then hands it to the platform for sandboxed execution, versioning and diffs. Reproducing an uploaded IFC (bootstrap) likewise goes through a skill-authored script.
