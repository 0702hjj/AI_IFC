---
name: aidxfv2
description: Generate, regenerate, and validate 2D DXF drawings from Python ezdxf sources. Use for DXF files, gen_dxf() sources, 2D profiles, outlines, templates, gaskets, panels, flat patterns, laser/plasma/waterjet cut layouts, and 2D drawing exports. Also for architectural floor plans and building drawings (平面图, 建筑平面, 户型图, 商场/购物中心/mall, 住宅/residence/ADU, doors/windows 门窗, walls 墙体) with standard drafting via the vendored archdxf library, including the step-routed building pipeline (plan.json 对齐 → 草案 → 确认 → 逐层 DXF → building.json 交付, plan→cad→bim 管线的 cad 段).
license: MIT
compatibility: Self-contained runtime (scripts/dxf + vendored slim cadpy); only external dependency is ezdxf.
metadata:
  project: aidxfv2
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

When the task is a building/architectural drawing (floor plans, 平面图, malls, residences), follow the **Building pipeline** below — it is step-routed and ordered. Standalone DXF work (single edits, symbols, generic drafting not tied to a building plan) skips the pipeline and follows the rules here directly.

Rules:

- **Building components (walls, openings, doors, windows, fixtures, dimension chains) MUST be constructed by calling `archdxf`** — never hand-write per-wall orientation math or cover-up geometry. Declarations (which wall, what opening, where) are yours; construction expansion is the library's.
- Openings are declared as (wall, offset, width) triples; positions are computed at declaration time, not at draw time.
- After generation, canonicalize for byte-identical reruns: `from archdxf.canon import canonicalize_dxf; canonicalize_dxf(path)`.

## Building pipeline (step-routed, mandatory)

plan → cad → bim 管线的 cad 段。Load only the current step file; the 落盘文件
(plan.json → building.json) is the run state — never rely on session memory
(contract: `references/plan_contract.md`).

| Step | File | 输入 → 输出 |
|---|---|---|
| 0 对齐 plan | `steps/step-00-ingest-plan.md` | plan.json 校验 + 按状态机路由 |
| 1 草拟方案 | `steps/step-01-draft-type.md` | 类型包选型 + draft 写回 plan.json |
| 2 交互确认 | `steps/step-02-confirm.md` | 用户修订 → confirmed: true 冻结 |
| 3 构建 | `steps/step-03-build.md` | 脚手架逐层生成 DXF（T0/校验门禁） |
| 4 交付 | `steps/step-04-deliver.md` | building.json + DXF 集（bim 的输入） |

Start at step 0; step 0 routes by plan.json state, so an interrupted run resumes
at the right step. If the user hands you a plan.json already `confirmed: true`,
step 0 routes straight to step 3.

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

## Visual self-review (LLM-only aid)

The render is for YOUR eyes only — users view the bare DXF in the frontend, so a preview is never a deliverable and never required output. Use it when layout judgment from numbers alone is ambiguous (annotation collisions, symbol orientation, overall proportions); skip it when the declaration and readback checks already answer everything.

The `aiblueprint` MCP (installed alongside this skill) is the render channel — do not hand-write matplotlib scripts:

```
aiblueprint_drawing open   {path: "<output>.dxf"}
aiblueprint_view screenshot          # quick in-memory PNG
aiblueprint_view preview             # LibreCAD render, saved files
```

`screenshot` is the default; use `preview` when the matplotlib render hides something (hatches, lineweights). Query helpers on the same MCP (`aiblueprint_entity list/get/measure`, `aiblueprint_drawing info`) double as readback checks.

## Final response

Final responses should include generated files, validation actually run, and assumptions.
