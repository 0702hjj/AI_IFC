# Massing: Mirror Symmetry

Build one half of a symmetric building, then mirror it across a central axis to get the other half. Openings are mirrored **per-opening** (projection onto the host wall), not by whole-wall coordinate matching.

## Parameters

| Parameter | Range | Default | Note |
|---|---|---|---|
| Mirror axis | building centreline | `MIRROR_X` | the X (or Y) coordinate of symmetry |
| Match tolerance | 100–300mm | 150mm | max distance from point to host wall axis |
| Scope | whole half / partial | — | full-wing or local symmetry |

## Technical Mapping

| Task | Approach | Note |
|---|---|---|
| Mirror walls | reflect axis endpoints across the axis | trivial for non-crossing walls |
| Mirror openings | **per-opening projection** onto the nearest host wall | the robust method |
| Host lookup | parametric projection `t` + perpendicular distance | find which mirrored wall hosts the opening |

**Why per-opening (not whole-wall)**: whole-wall coordinate matching fails on walls that **cross the mirror axis** (long walls) and on shaft walls whose mirrored length differs (mismatch 240–2400mm). Instead: take each opening's absolute centre on the source wall, mirror it about the axis, then **project** it onto the nearest host wall whose axis passes through the mirrored point, and recompute its `along` distance along that host wall's axis.

## Example Code

```python
import numpy as np
MIRROR_X = -1042.0   # symmetry axis (mm); mirrored x = 2*MIRROR_X - x

def mirror_host(px, py, east_walls, tol=150):
    """Find the host wall whose axis passes through (px,py), point inside the segment.
    Returns (wall_index, along_from_start, distance) or None."""
    best = None
    for j, we in east_walls:
        (x1, y1), (x2, y2) = we["axis"][0], we["axis"][-1]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx*dx + dy*dy
        if L2 == 0:
            continue
        t = ((px - x1)*dx + (py - y1)*dy) / L2          # projection parameter
        if t < -0.05 or t > 1.05:                        # outside the wall segment
            continue
        dist = ((px - (x1 + t*dx))**2 + (py - (y1 + t*dy))**2) ** 0.5
        if dist < tol and (best is None or dist < best[2]):
            best = (j, t * (L2 ** 0.5), dist)
    return best

# For each opening on the source (west) half: absolute centre → mirror → project onto east host.
for w in west_walls:
    (x1, y1), (x2, y2) = w["axis"][0], w["axis"][-1]
    dx, dy = x2 - x1, y2 - y1
    L = (dx*dx + dy*dy) ** 0.5
    for op in w["openings"]:
        ax = x1 + (op["along"] / L) * dx                 # absolute centre (west)
        ay = y1 + (op["along"] / L) * dy
        host = mirror_host(2*MIRROR_X - ax, ay, east_walls)   # mirrored point → east host
        if host:
            j, along_new, _ = host
            # assign op to east_walls[j] with along = along_new
```

## Variations

- **Whole-wing mirror** — a building with two symmetric wings (E/W) about a central core.
- **Partial mirror** — only a facade bay or a floor plate is mirrored.
- **Double symmetry** — symmetric about both X and Y axes (cruciform / courtyard plans).
