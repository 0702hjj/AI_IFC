# Pipeline Pitfalls & Fixes — 流程 bug 及解决方法(可累加)

> 逆向/正向实战中踩过的坑。**可累加**: 发现新 bug 就在对应分类下补一条(现象 → 根因 → 解决 → 来源)。
> 分类: G=Geometry 几何 / O=Opening 开洞 / M=Mirror 镜像 / P=Performance 性能 / S=Stair 楼梯 / R=Roof 屋顶

---

## G. Geometry(几何)

### G1. Stair flight tessellation bug
- **Symptom**: extruding a sawtooth profile on `IfcStairFlight` yields an extra vertex at the origin, corrupting geometry.
- **Fix**: build **each step as its own box** via `add_wall_representation` (pure translation, no rotation). Never extrude a sawtooth profile for a flight.
- **Source**: ShangzhuLou `sawtooth_run`

### G2. Arbitrary profile instability
- **Symptom**: slabs / landings / boxes built with `add_arbitrary_profile` occasionally tessellate wrong.
- **Fix**: use a **parametric rectangle profile** (`IfcRectangleProfileDef`, XDim/YDim in mm, depth in m) for any rectangular box.
- **Source**: ShangzhuLou `box`

### G3. Sloped members can't use axis-aligned extrude
- **Symptom**: pitched roof deck / louver blades are sloped; `add_wall_representation` is axis-aligned only.
- **Fix**: use a **Brep** (verts+faces via `add_mesh_representation`, `force_faceted_brep=True`) or a **rotated matrix** `M = T @ Ry(tilt) @ Rz(phi)` / louver chain `fm @ T @ Rx`.
- **Source**: Castle sporenkap / ShangzhuLou louver

## O. Opening(开洞)

### O1. Opening doesn't penetrate
- **Symptom**: the void stops partway through the wall.
- **Fix**: opening thickness **≥ 1.5× wall thickness**.

### O2. Opening double-offset
- **Symptom**: opening lands one wall-origin away from where intended.
- **Fix**: set **world coordinates** before `feature.add_feature` (auto-converts world→wall-relative). Never hand-set wall-local coords.

### O3. Double-run stair slab openings alternate
- **Symptom**: stair shaft opening on the wrong lane for a floor.
- **Fix**: openings **alternate by floor** (arrival lane vs departure lane) and extend ~300mm past the last tread; cap the top floor with a roof slab instead of an opening.
- **Source**: ShangzhuLou

### O4. IFC2X3 opening bbox is empty
- **Symptom**: `IfcOpeningElement` has no own geometry → bbox comes back empty.
- **Fix**: derive the opening position from the **door/window bbox** instead.
- **Source**: Duplex

## M. Mirror(镜像)

### M1. Whole-wall mirror matching fails
- **Symptom**: walls crossing the mirror axis, or shaft walls of unequal length, mismatch by 240–2400mm.
- **Fix**: mirror **per-opening** — project each opening's absolute centre across the axis onto the nearest host wall (`_mirror_host`).
- **Source**: ShangzhuLou

## P. Performance(性能)

### P1. Large model is slow / hangs at exit
- **Symptom**: hundreds of elements → slow build; process hangs at the end.
- **Fix**: performance trio — **type-level material** (assign material to IfcType, keep pset on instances), **deferred container** (accumulate + one manual `IfcRelContainedInSpatialStructure` flush), **`os._exit`** after `sys.stdout.flush()`. See `performance.py`.
- **Source**: ShangzhuLou

## S. Stair(楼梯)

_(待补: 楼梯建造相关坑, 如楼梯间与隔间墙协调、扶梯井开洞)_

## R. Roof(屋顶)

_(待补: 屋顶建造相关坑, 如坡板拼接、老虎窗定位)_

---

**累加规则**: 新 bug 按分类(G/O/M/P/S/R)补一条 `### X#. 标题` + Symptom/Fix/Source; 跨类新主题新增 `## 分类` 节。
