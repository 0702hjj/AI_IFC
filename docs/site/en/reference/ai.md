# AI Integration

An integration guide for AI agents: use REST to drive the IFC editing service through the full "edit attribute → pending → commit → diff" flow. The machine-consumable schema: [OpenAPI Files](/en/reference/openapi).

## One API, two roles

Humans (browser) and AI agents use the **same editing endpoints**; only the entry point and `provenance.source` differ:

```
Browser (human) ──► Go server :8090 ──proxy──► Python edit-service :8100
                  /api/v1/models/{id}/edit/...        │  /models/{id}/...
AI agent ────────► REST direct ────────────────────┘  (or via the Go proxy, one-to-one)
```

- Human: browser → Go proxy; after commit Go writes the change log and triggers XKT reconversion.
- AI: REST directly to edit-service (default `http://127.0.0.1:8100`) with `provenance.source="AI"`; the Go proxy works too.
- The Python service ships Swagger UI (`/docs`) and the raw schema (`/openapi.json`).

## Quick start

```bash
# 1) Python edit service (default port 8100)
cd viewer/edit-service
uv sync
uv run uvicorn app.main:app --port 8100

# 2) Go server (default 127.0.0.1:8090)
cd viewer/server
go run ./cmd/server
```

**dataDir consistency**: `VIEWER_DATA_DIR` must point to the same directory as the Go `server_config.json` `dataDir` (both locate model files at `{dataDir}/uploads/{id}.ifc`).

## Direct AI flow (curl)

Prerequisite: a model exists (id like `m_` + 16 lowercase hex) with its file at `{VIEWER_DATA_DIR}/uploads/{id}.ifc`.

```bash
BASE=http://127.0.0.1:8100
MID=m_0123456789abcdef
GUID='2O2Fr$t4X7ZfFPoeewFlqU'   # IFC GlobalId

# 1. Edit attribute → pending (in-memory only, no disk write)
curl -X PUT "$BASE/models/$MID/entities/$GUID" \
  -H 'Content-Type: application/json' \
  -d '{
        "fields": {"Name": "Basic Wall:AI"},
        "psets":  {"Pset_WallCommon": {"FireRating": "2h"}},
        "author": "ai-agent",
        "provenance": {"source": "AI"}
      }'

# 2. Inspect pending
curl "$BASE/models/$MID/pending"

# 3. Commit: atomic write + version snapshot + history
curl -X POST "$BASE/models/$MID/commit"

# 4. Versions and diff
curl "$BASE/models/$MID/versions"
curl -X POST "$BASE/models/$MID/diff" \
  -H 'Content-Type: application/json' \
  -d '{"base": "v1", "target": "current"}'
```

> A direct commit does **not** trigger the Go change log or XKT reconversion. For the full pipeline (visible to the frontend) use the Go proxy: `http://127.0.0.1:8090/api/v1/models/$MID/edit/...`.

## Provenance and the commit model

- `provenance.source`: enum `UI | AI`, default `UI`. **AI calls must pass `"AI"`**. It is a declared field without anti-forgery semantics (no auth in v1).
- `author`: free text, default `local-user`.
- Two-phase semantics: PUT only changes the in-memory model and records pending; commit persists to disk, creates a version snapshot and writes history.
- Commit model (Go change log): each entry has `author` / `createdAt` / `operation` (`update | migrate`) / `diff` / `provenance`.
- Python history and the Go change log are two records: history = one entry per PUT (with a changes array); change log = one entry per field change.

## Versions and diff semantics

- Snapshots live at `{VIEWER_DATA_DIR}/models/{id}/versions/v{n}.ifc` (n from 1, append-only, atomic writes).
- First commit: the original upload is snapshotted as v1, then the new file as v2; every later commit produces v{n+1}.
- Diff is keyed by GlobalId; changed entities reduce to field-level old→new for direct and pset attributes; entity reference attributes (geometry representation) are excluded.
- Snapshot-to-snapshot diff results are cached in `versions/diff-{base}-{target}.json`; `target="current"` is not cached.

## Limits and roadmap

v1 limits (details in [Known limitations](/project/known-limits), Chinese): single-machine single-user, no auth (do not expose publicly); `VIEWER_DATA_DIR` must equal the Go `dataDir`; diff is attribute-level only.

Roadmap (not delivered yet): an MCP wrapper (REST+MCP dual exposure, modeled on ifcmcp's tool patterns) and a sandbox/execution endpoint — see [Roadmap](/project/roadmap) (Chinese).

## Division of labor with the aiifc skill

The REST editing API fits fine-grained edits (attributes / psets of an existing model). For **building models from scratch or large geometry changes**, use the [AI Skill (aiifc)](/en/reference/ai-skill) — the agent writes `ifcopenshell.api` code directly to produce a complete IFC file, then hands it to the platform for commit / version / reconversion.
