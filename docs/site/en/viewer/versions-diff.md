# Versions & Diff Viewer

## Version snapshots

Each commit produces an immutable version snapshot — append-only, written atomically:

- First commit: the original upload is snapshotted as `v1`, and once the write has landed the new file is snapshotted as `v2`.
- Each subsequent successful commit produces `v{n+1}`.
- Snapshots are stored at `{dataDir}/models/{id}/versions/v{n}.ifc`.

## Diff panel

The "Diff" toolbar button opens the comparison panel:

1. Choose a base (v1 / v2 / …) and a target (a version or `current`).
2. Click "Compare": **green = added, yellow = modified, red = removed**.
3. Click an entry to locate the element; modified entries expand to field-level old → new.
4. "Clear" resets the coloring.

## Diff semantics

- **GlobalId** is the entity identity: `added` / `removed` are guid lists; `changed` is field-level old → new over direct attributes and pset attributes.
- Based on ifcdiff, run with only the `attributes` / `property` relationships; entity reference attributes (ObjectPlacement, Representation and other geometry-representation layers) are not compared — **no geometric diff is currently provided**.
- Removed elements no longer have geometry in the current XKT, so they only appear in the red list (design decision).
- When both base and target are immutable versions, the result is cached at `versions/diff-{base}-{target}.json`; `target="current"` is not cached.

For the endpoint contract see [IFC Editing API](/en/reference/edit-api).
