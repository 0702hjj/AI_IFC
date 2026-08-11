# DXF validation checklist

Deterministic readback validation for generated `.dxf` artifacts. Validation decides pass/fail from `ezdxf` checks, never from eyeballing the source or the generator's stdout. Report only checks that actually ran.

## Mandatory baseline (run for every generated DXF)

1. **File reads back**: `ezdxf.readfile(path)` succeeds; consider `ezdxf.audit()` for structural errors.
2. **Units**: `doc.header["$INSUNITS"]` matches the brief (4 = millimeters when `doc.units = ezdxf.units.MM`).
3. **Entity inventory**: counts by entity type and by layer match the brief.

```python
from collections import Counter

doc = ezdxf.readfile("out.dxf")
msp = doc.modelspace()
by_type = Counter(e.dxftype() for e in msp)
by_layer = Counter(e.dxf.layer for e in msp)
```

4. **Closed cut profiles**: every profile intended for cutting is closed.

```python
open_polylines = [e for e in msp.query("LWPOLYLINE") if not e.closed]
```

5. **Drawing extents**: computed extents match the expected outline size.

```python
from ezdxf import bbox

extents = bbox.extents(msp)
width = extents.extmax.x - extents.extmin.x
height = extents.extmax.y - extents.extmin.y
```

## Spec-driven checks (one per user-specified dimension)

Convert every dimension in the brief into a concrete assertion, for example:

- Overall width/height from extents (with tolerance, e.g. `abs(actual - expected) < 1e-6`).
- Hole count, diameters, and center coordinates from `CIRCLE` entities on the expected layer.
- Slot length/width from polyline segment analysis.
- Feature counts per layer (e.g. number of bend lines on the bend layer).

```python
holes = sorted(
    ((e.dxf.center.x, e.dxf.center.y, e.dxf.radius * 2) for e in msp.query('CIRCLE[layer=="CUT"]')),
    key=lambda h: (h[0], h[1]),
)
assert len(holes) == 4
assert all(abs(d - 8.0) < 1e-6 for _, _, d in holes)  # M8 clearance holes
```

## Layer rules

- Cut geometry and bend/fold lines live on separate layers.
- Bend-layer names must contain `bend` (case-insensitive) so downstream tools classify them as bends rather than cuts. The vendored render payload (`scripts/dxf/render_payload.py`) uses the same rule: layer name contains "bend" → semantic kind `bend`, otherwise `cut`.
- Check that every entity sits on an intended layer; flag stray entities on layer `0` unless the brief says otherwise.

## Audit mode

```python
auditor = doc.audit()
for error in auditor.errors:
    ...  # structural problems ezdxf detected
```

## Failure handling

- A failed check means: fix the Python generator source, regenerate with `scripts/dxf`, re-run the full check set. Never hand-edit the `.dxf`.
- After a fix, re-run **all** checks, not only the one that failed — regeneration rewrites the whole artifact.

## Reporting discipline

- Report only checks that actually ran, with their outcomes.
- List assumptions made (default layer names, tolerances, units) when the brief did not specify them.
