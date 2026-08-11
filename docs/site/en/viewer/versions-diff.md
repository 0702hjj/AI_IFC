# Versions & Diff Viewer

## Version snapshots

For script-backed models, a **big version** is an explicit "save version":

- Script and locate map are **kept in full**: `{dataDir}/models/{id}/scripts/v{n}.py` + `v{n}.map.json` (+ `v{n}.meta.json` notes), numbered in lockstep, append-only and written atomically.
- Only the **latest IFC is materialized**: `versions/v{n}.ifc` keeps just the newest big version; historical IFC snapshots are rebuildable cache — diffing/downloading an old version re-runs its script in the sandbox (results cached in `ifc_cache/`, LRU capacity 4). Rebuilt files are only **semantically equal** to the original snapshots (deterministic GlobalIds keep them aligned; header timestamps differ), so comparisons always use semantic diff, never byte equality.
- Legacy entity-edit snapshots without a script (migration-period state) are preserved.
- Staging steps (small versions) produce no snapshots — only lightweight script diffs between steps; the 10-step ring drops the oldest step, and save compacts the chain into a big version.

Plain models (external uploads without a script) have no big-version chain.

## Diff panel

The "Diff" toolbar button opens the comparison panel:

1. Choose a base (v1 / v2 / …) and a target (a version or `current`).
2. Click "Compare": **green = added, yellow = modified, red = removed**.
3. Click an entry to locate the element; modified entries expand to field-level old → new.
4. "Clear" resets the coloring.

## Diff semantics

- **GlobalId** is the entity identity: `added` / `removed` are guid lists; `changed` is field-level old → new over direct attributes and pset attributes.
- Based on ifcdiff, run with only the `attributes` / `property` relationships; entity reference attributes (ObjectPlacement, Representation and other geometry-representation layers) are not compared. **No geometric diff is provided** — the IFC is a script artifact, changing geometry means changing the script (see [IFC Script Editing](/en/viewer/editing)); diffs are script diff + attribute-level semantic diff.
- Removed elements no longer have geometry in the current XKT, so they only appear in the red list (design decision).
- When both base and target are immutable versions, the result is cached at `versions/diff-{base}-{target}.json`; `target="current"` is not cached.
- When a historical version's IFC is not on disk, diffing triggers an on-demand rebuild (see above); big versions also have a script diff (text + PARAMS key-level) — see [Script editing & version diff](/en/reference/design-edit).

For the endpoint contract see [IFC Editing API](/en/reference/edit-api).
