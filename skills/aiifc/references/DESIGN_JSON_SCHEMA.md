# Design JSON Schema — LLM Intent Contract

> The LLM writes a **design JSON** (parametric geometric intent, **no coordinate math**); `flows/design_builder.py` normalizes it into `features.json`. This file is the contract for what a valid design JSON looks like. Read it before producing a design JSON.
>
> **A design JSON is the output of a design decision, not a fixed layout**: first *choose* the building's massing / facade / roof / stairs / windows from `DESIGN_PATTERNS.md` (concept patterns) and `docs/design/` (component recipes), then express that chosen design as this JSON. Don't invent a layout from thin air.

- Units: metres (builder snaps to `meta.modulus`). Give approximate values; the builder anchors them.
- Principle: describe **where / how big** (axes, outlines, along-axis positions, axis-grid paths), never compute coordinates.

---

## Top-level structure

```json
{
  "meta":   { "units": "m", "modulus": 0.1, "name": "my_building" },
  "frame":  { "footprint": [...], "storeys": {...}, "axis_grid": {...} },
  "floors": {
    "1F": { "walls": [...], "openings": [...], "slabs": [...], "stairs": [...], "roof": {...} },
    "2F": { ... }
  }
}
```

## meta

| field | type | default | meaning |
|---|---|---|---|
| `units` | str | `"m"` | always metres |
| `modulus` | float | `0.1` | snap grid (m); builder anchors all lengths to it |
| `name` | str | `"building"` | building name |

## frame (whole building, replaces wrapping)

| field | type | required | meaning |
|---|---|---|---|
| `footprint` | `[[x,y],...]` | ✅ | outer closed outline (world coords, approximate; builder snaps + closes) |
| `storeys` | `{"1F":0.0, "2F":3.0}` | ✅ | storey name → elevation (m) |
| `axis_grid` | `{"x":[...], "y":[...]}` | optional | axis lines for interior walls / stairs (values snapped) |
| `typical` | `{"STD": ["2F","3F",...]}` | optional | typical-floor map: a `floors` key → the storeys it replicates to (for standard floors) |

> **Standard floors (typical)**: multi-storey buildings often repeat one layout. Write the typical floor ONCE under a `floors` key like `"STD"`, and list the storeys it applies to in `frame.typical`. The builder replicates it to each storey (each gets its own elevation). Difference floors (ground / top) are written under their own storey names.

## floors.<storey>.walls — 4 forms

Every wall has `t` (thickness, m) and `kind` (`"ext"`/`"int"`). Pick ONE geometry form:

| form | field | use for | example |
|---|---|---|---|
| straight | `axis: [[x1,y1],[x2,y2]]` | exterior walls, single interior walls (can hold openings) | `{"axis":[[0,0],[12,0]],"t":0.2,"kind":"ext"}` |
| polyline (sloped) | `axis: [[...],[...],[...]]` | sloped/zigzag walls (any angle) | `{"axis":[[4,0],[4,6],[8,6]],"t":0.12,"kind":"int"}` |
| **axis-grid path** | `path: [{"x":i,"y":j},...]` | **partition-wall runs** (orthogonal, no coords) | `{"path":[{"x":1,"y":0},{"x":1,"y":2},{"x":2,"y":2}],"t":0.12,"kind":"int"}` |
| arc | `arc: {center,r,a0,a1}` | curved walls | `{"arc":{"center":[12,4],"r":3.0,"a0":0,"a1":180},"t":0.12,"kind":"int"}` |

- `path` points index into `axis_grid` (`{"x":i,"y":j}` = `(axis_grid.x[i], axis_grid.y[j])`); adjacent points must share one axis (orthogonal). This is how you describe a partition run (L/U-shape) **without coordinates**.
- `arc` angles in degrees; builder approximates with ~12° chord segments.

### `key` — 构件稳定标识（跨版本 diff 的地基）

每个构件（wall / opening / slab / stair）可带 `key`（如 `"1F:wall:2"`、`"1F:opening:0"`）：

- **提供时**：builder 原样保留；**编辑时 key 不变**（插入新元素才分配新 key）→ 跨版本稳定。
- **缺省时**：builder 自动分配 `{storey}:{kind}:{n}`（n 为本层该类型的序号，0 起）。
- **约定**：`key` 必须**稳定且唯一**（同一建筑内）。建议格式 `<storey>:<kind>:<n>`。
- 作用：
  1. `build_script_template.py` 用 `uuid5(NAMESPACE_AI_IFC, key)` 生成**确定性 GlobalId**（同一 key 多次运行 GlobalId 不变）。
  2. 生成时写入 `Pset_AIIFC.designKey`，实现 **IFC 构件 ↔ design JSON 条目 双向映射**。
  3. 大版本 diff 按 `key` 对齐（而非随机 GlobalId）。

```json
{"axis":[[0,0],[12,0]],"t":0.2,"kind":"ext","key":"1F:wall:0"}
```

## floors.<storey>.openings

| field | type | default | meaning |
|---|---|---|---|
| `wall` | int | — | index into this storey's `walls` array (host wall) |
| `along` | float | — | distance along the wall axis from its start (m) — **parametric, no XY** |
| `w` / `h` | float | — | width / height (m) |
| `sill` | float | `0.0` | sill height (door=0, window≈0.9) |
| `type` | str | `"window"` | `door` / `window` |

## floors.<storey>.slabs

| field | type | default | meaning |
|---|---|---|---|
| `profile` | `[[x,y],...]` | = footprint | slab outline (omit for full-footprint slab) |
| `t` | float | `0.15` | thickness (m) |
| `predef` | str | `"FLOOR"` | `FLOOR` / `ROOF` / `LANDING` |

## floors.<storey>.stairs / roof (mark position/class only)

Stairs and roofs are **marked, not built here** — the build script constructs them from `docs/design/` recipes. A stair marks its **space occupancy** in ONE of two ways, chosen by the stair's role (don't force every stair into one template):

```json
"stairs": [
  {"shaft":{"x":[1,2],"y":[0,3]}, "type":"double_run", "width":1.1},
  {"at":[6,4], "size":[2,3], "type":"spiral"}
]
"roof":   {"type":"gable", "slope":35, "ridge_h":2.5, "overhang":0.4}
```

- **`shaft` (axis-grid indices — for enclosed/egress stairs)**: `{x:[i,j], y:[k,l]}` — the shaft rectangle sits between `axis_grid.x[i]↔x[j]` and `axis_grid.y[k]↔y[l]`; its boundaries ARE wall axes, so the stair is born hugging existing walls. Use for `double_run` / `straight` egress stairs that belong in a wall-framed shaft. Requires `frame.axis_grid`. **Shaft enclosure (extra surrounding walls) is OPTIONAL** — the boundary axes are already walls; do NOT add a second thin cavity wall.
- **`at` + `size` (free position — for open / spiral / cantilever / escalator stairs)**: `at:[x,y]` anchor, `size:[w,l]` footprint. Free-standing, NOT wall-bound — for spiral stairs, cantilevered/suspended stairs, open-atrium ramps, mall escalators that sit in open space with no wall-framed shaft.
- `type`: `double_run` / `straight` (egress → use `shaft`) · `spiral` / `cantilever` / `escalator` (open → use `at`)
- `width`: tread width (m), for run-based types.

Pick the form matching the stair's role: an open spiral must NOT be forced into a wall shaft; an egress stair must NOT be left free-floating.

(`roof.type`: flat / gable / hip / shed.)

---

## Normalization rules (what design_builder checks)

0. **Typical floors**: a `floors` key present in `frame.typical` (e.g. `"STD"`) is replicated to every storey in `frame.typical["STD"]`; other keys are used as-is for their own storey
1. `footprint` snaps to modulus, must close into a simple polygon (≥3 pts, no self-intersection)
2. `storeys` elevations snapped + sorted
3. `path` adjacent points must share an axis (else `SchemaError` → use `axis` polyline)
4. `arc` → multi-segment chord approximation
5. Any failure → `SchemaError` → the LLM re-emits a corrected design JSON (Self-Refine loop)

## Full example (2-storey, L-partition, one window)

```json
{
  "meta": {"units":"m","modulus":0.1,"name":"small_villa"},
  "frame": {
    "footprint": [[0,0],[12,0],[12,8],[0,8]],
    "storeys": {"1F":0.0,"2F":3.0},
    "axis_grid": {"x":[0,4,8,12],"y":[0,4,8]}
  },
  "floors": {
    "1F": {
      "walls": [
        {"axis":[[0,0],[12,0]],"t":0.2,"kind":"ext"},
        {"axis":[[12,0],[12,8]],"t":0.2,"kind":"ext"},
        {"axis":[[12,8],[0,8]],"t":0.2,"kind":"ext"},
        {"axis":[[0,8],[0,0]],"t":0.2,"kind":"ext"},
        {"path":[{"x":1,"y":0},{"x":1,"y":2},{"x":2,"y":2}],"t":0.12,"kind":"int"}
      ],
      "openings": [
        {"wall":0,"along":6.0,"w":1.0,"h":2.1,"sill":0.0,"type":"door"},
        {"wall":2,"along":3.0,"w":1.5,"h":1.5,"sill":0.9,"type":"window"}
      ],
      "slabs": [{"t":0.15,"predef":"FLOOR"}],
      "stairs": [{"at":[9.0,5.0],"shaft":{"w":2.0,"l":4.0},"type":"double_run"}]
    },
    "2F": {
      "walls": [
        {"axis":[[0,0],[12,0]],"t":0.2,"kind":"ext"},
        {"axis":[[12,0],[12,8]],"t":0.2,"kind":"ext"},
        {"axis":[[12,8],[0,8]],"t":0.2,"kind":"ext"},
        {"axis":[[0,8],[0,0]],"t":0.2,"kind":"ext"}
      ],
      "openings": [{"wall":2,"along":6.0,"w":1.5,"h":1.5,"sill":0.9,"type":"window"}],
      "slabs": [{"t":0.15,"predef":"FLOOR"}],
      "roof": {"type":"gable","slope":35,"ridge_h":2.5,"overhang":0.4}
    }
  }
}
```

## Related

- `MODELING_WORKFLOWS.md` → Design JSON 框定(two-step method, downstream build script)
- `flows/design_builder.py` — normalizer (design JSON → features.json)
- `docs/design/README.md` — component-building recipes the build script uses
