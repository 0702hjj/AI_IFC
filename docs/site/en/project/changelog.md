# Changelog

Major changes per release. Full history in the [GitHub commit log](https://github.com/0702hjj/AI_IFC/commits/main).

## Unreleased (v0.2 in progress)

**Script-as-source unified editing (web edit = edit the script)**

- Locate an element's script callsite: `GET /script/locate?guid=` (guid→designKey→line/col/snippet/origin); PropertyPanel is read-only with a "Locate script" jump into the Design panel's script editor.
- New `POST /script/edit-call` (edit-service direct): lossless libcst scalar-argument rewrite + sandbox validation + staging; new contract clauses C-locate (#30, elements via the `create_entity` factory) and C-scalar (#31, web-editable parameters are scalars/PARAMS references).
- Big versions as a lockstep trio: `scripts/v{n}.py` + `v{n}.map.json` kept in full; `versions/v{n}.ifc` materializes only the latest, history rebuilt on demand (`ifc_cache/` LRU 4).
- Bootstrap: the first script staging on a plain model preserves the original upload as `bootstrap.ifc`; the first save response carries an `alignment` count.
- **L1 direct-edit chain retired (410 Gone)**: `PUT/DELETE /entities/{guid}`, `editable-schema`, `POST /commit` and the Go-side direct-edit proxy routes are gone (recovery anchor `fb55a8a`); `POST /diff` (IFC semantic diff) and `POST /diff/upload` are kept.

**Script-as-source (M5)**

- Python build scripts became the single source of truth for IFC: script contract (PARAMS + deterministic GlobalIds + build entry), sandboxed script execution, WPS-style script staging + paired major-version snapshots (`scripts/v{n}.py` + `versions/v{n}.ifc`).
- Script diffs (text + PARAMS key-level, major/minor two levels); Design panel rebuilt as a PARAMS form + script editor; the design JSON editing pipeline was removed.

**MCP & user provenance**

- New `mcp-server`: a thin MCP wrapper (stdio) around the editing API that parses user-modified IFC/DXF files and tags them with `USER` provenance (extended from `UI`/`AI`).

**Direct real property editing**

- Property editing no longer has an override layer — it goes straight through the pending → commit real-edit loop; new editable-schema and element-deletion endpoints; PropertyPanel rebuilt with typed forms.

**Fixes & misc**

- ChatSidebar history/SSE merge fixes and EventSource resilience with reconnect.
- edit-service image ships bwrap and binds to loopback; CI gained an mcp-server job and a real compose smoke test.

## v0.1.0 (2026-08, first public release)

**Review platform**

- IFC upload with queued conversion (XKT geometry + semantic metadata); model tree, property inspection, visibility tools, section planes, measurements, NavCube.
- Issues & 3D pins with camera view and screenshot capture, status flow, click-to-locate.
- File / PostgreSQL dual implementations for issues, overrides and change log.

**Real IFC editing & versions**

- edit-service (FastAPI + IfcOpenShell): property overrides and a two-phase pending → commit real-edit flow, immutable version snapshots, attribute-level semantic diffs keyed by GlobalId, Diff Viewer.

**AI integration**

- Humans and AI share the same REST editing API (distinguished by provenance), with an OpenAPI tool catalog and integration guide.
- The aiifc modeling skill: agent-agnostic, lets AI write `ifcopenshell.api` code directly to generate or heavily modify IFC models; includes a Plan → DXF → IFC three-stage orchestration workflow and a DXF generator.
- Deterministic element identity: stable `key` → `uuid5` deterministic GlobalId → `Pset_AIIFC.designKey` bidirectional mapping.

**Engineering**

- Uniform versioned API `/api/v1/{resource}/{id}` with the Go server as the single entry point and a unified envelope contract.
- Self-contained dependencies (ifcopenshell / ifcdiff / ifcquery all from PyPI); this VitePress documentation site with an English locale and machine-generated API reference with CI drift detection.
- Legacy SCAD code moved to the private archive repo [0702hjj/SimpleCADAPI-archive](https://github.com/0702hjj/SimpleCADAPI-archive); this repository focuses on the `viewer/` product.
