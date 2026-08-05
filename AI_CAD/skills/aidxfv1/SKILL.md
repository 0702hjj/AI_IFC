---
name: aidxfv1
description: Generate, regenerate, and validate 2D DXF drawings from Python ezdxf sources. Use for DXF files, gen_dxf() sources, 2D profiles, outlines, templates, gaskets, panels, flat patterns, laser/plasma/waterjet cut layouts, and 2D drawing exports. Also for architectural floor plans and building drawings (平面图, 建筑平面, 户型图, 商场/购物中心/mall, 住宅/residence/ADU, doors/windows 门窗, walls 墙体) with standard drafting via the vendored archdxf library.
license: MIT
compatibility: Self-contained runtime (scripts/dxf + vendored slim cadpy); only external dependency is ezdxf.
metadata:
  project: aidxfv1
  upstream: earthtojake/text-to-cad (skills/dxf)
---

# DXF generation and validation (aidxfv1)

Provenance: forked and slimmed from [earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad) `skills/dxf` (MIT). This skill is fully self-contained: the runtime is vendored under `scripts/` and there are no cross-skill dependencies.

## Purpose

Create or modify 2D DXF drawings from natural-language requirements, generate validated `.dxf` artifacts, and return checked outputs. DXF sources are Python files defining `gen_dxf()` returning an `ezdxf` document; the CLI owns output paths.

## Use this skill when

Use this skill when the user asks for DXF files, 2D drawings, profiles, outlines, templates, gaskets, panels, flat patterns, or cut layouts for laser, plasma, waterjet, or CNC routing.

## Environment

The runtime needs `ezdxf` and the vendored `cadpy` package. Install once into the skill venv (or reuse an interpreter that already has them):

```bash
uv pip install -r requirements.txt
```

`requirements.txt` installs `ezdxf` plus the vendored `cadpy` via `--editable ./scripts/packages/cadpy` and the vendored `archdxf` via `--editable ./scripts/packages/archdxf`. No other dependencies (no build123d/OCP needed — this is the DXF-only closure).

## Architectural drafting (building plans)

When the task is a building/architectural drawing (floor plans, 平面图, malls, residences), apply the three-layer chain before writing any geometry:

1. Read `references/vocabulary.md` — take component words from the enumerations (door/window/swings/fixtures/detectors); do not invent vocabulary.
2. Read `references/floor_plan_assembly.md` — the assembly invariant (declaration formats, construction order, self-check list).
3. Read `references/archdxf_api.md` — the call signatures of the vendored `archdxf` library.

Rules:

- **Building components (walls, openings, doors, windows, fixtures, dimension chains) MUST be constructed by calling `archdxf`** — never hand-write per-wall orientation math or cover-up geometry. Declarations (which wall, what opening, where) are yours; construction expansion is the library's.
- Openings are declared as (wall, offset, width) triples; positions are computed at declaration time, not at draw time.
- After generation, canonicalize for byte-identical reruns: `from archdxf.canon import canonicalize_dxf; canonicalize_dxf(path)`.
- If a building type package exists under `references/building_types/`, read it for type-specific values; if the task exceeds a package's declared scope, say so instead of bending the vocabulary.

## Defaults

Use these defaults unless the user specifies otherwise:

- Units: millimeters; set them explicitly on the document (`doc.units = ezdxf.units.MM`).
- Geometry lives in modelspace at 1:1 scale.
- Cut profiles are closed polylines or closed line/arc loops; open contours only for engraving or reference geometry.
- Layers carry intent: keep cut geometry and bend/fold lines on separate layers, and include "bend" in bend-layer names so downstream tools classify them as bends rather than cuts.
- DXF layers are drawing structure, not part/assembly structure.

## Tool

The launcher lives in the skill directory:

```bash
python scripts/dxf targets... [flags]
```

Use the active project Python interpreter (the one with `ezdxf` + `cadpy` installed); treat `python` as an interpreter placeholder, and use `--help` for the full interface. Target paths resolve from the command's current working directory; run from the workspace that owns the artifacts with cwd-relative target paths. Keep a DXF output and its Python generator in the same directory with the same basename unless the user requests otherwise.

A DXF target is a Python source defining:

```python
def gen_dxf():
    ...
    return document
```

Plain generated Python targets write sibling `.dxf` outputs. Use `-o`/`--output` only with one plain generated Python target, or use `SOURCE.py=OUTPUT.dxf` positional pairs for per-target custom outputs. Do not put output paths in the `gen_dxf()` return value.

`scripts/dxf` is a generator; it does not inspect existing `.dxf` files. For existing DXF inspection, use `ezdxf` readback checks (see `references/VALIDATION.md`).

## Workflow

1. Convert the request into a short brief: outline dimensions, holes and slots, layers, units, output path, and validation targets.
2. Write or edit the Python source with meaningful dimensions as named parameters.
3. Run `scripts/dxf` on explicit Python source targets only; do not run directory-wide generation.

```bash
python scripts/dxf path/to/source.py
python scripts/dxf path/to/source.py -o path/to/output.dxf
python scripts/dxf path/to/a.py=out/a.dxf path/to/b.py=out/b.dxf
```

4. Validate the generated DXF deterministically (see `references/VALIDATION.md`), then report.

## Validation

Verify the generated file with targeted `ezdxf` readback checks instead of eyeballing: entity counts by type and layer, closed flags on cut profiles, drawing extents, and every dimension the user specified. The full checklist lives in `references/VALIDATION.md` — read it before your first validation pass.

```python
import ezdxf

doc = ezdxf.readfile("path/to/output.dxf")
msp = doc.modelspace()
profiles = [e for e in msp.query("LWPOLYLINE") if e.closed]
holes = msp.query('CIRCLE[layer=="0"]')
```

Report only checks that actually ran.

## Source-of-truth discipline

- The Python generator source is the source of truth; the `.dxf` is a generated artifact. Edit source, not generated artifacts; regenerate after every change.
- The generator writes `cadpy:sourcePath` / `cadpy:sourceHash` provenance metadata into each `.dxf`; do not strip it.

## Visual self-review (optional)

For a quick visual check without any external viewer, render the DXF to PNG with `ezdxf.addons.drawing` and matplotlib when available:

```python
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
import matplotlib.pyplot as plt

doc = ezdxf.readfile("path/to/output.dxf")
fig = plt.figure()
ax = fig.add_axes([0, 0, 1, 1])
ctx = RenderContext(doc)
Frontend(ctx, MatplotlibBackend(ax)).draw_layout(doc.modelspace(), finalize=True)
fig.savefig("preview.png", dpi=150)
```

If matplotlib is not installed, rely on the deterministic `ezdxf` readback checks instead; do not skip validation because no preview was produced.

## Final response

Final responses should include generated files, validation actually run, and assumptions.
