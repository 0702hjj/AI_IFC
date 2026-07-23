# DXF → 单层建筑模型 技术选型研究总结

日期:2026-07-22
研究范围:`/CADapi` 下的 SimpleCADAPI、cad-to-shapely、IfcOpenShell(v0.8.0)三个开源库,
目标是为 "先生成 DXF 平面图 → 依据其几何约束完成单层建筑 3D 建模" 流水线选型。

---

## 1. 目标流水线

```
DXF(2D 平面图,分层约束:WALLS / DOORS / WINDOWS / COLUMNS ...)
  → [cad-to-shapely] DXF 解析 + polygonize
  → shapely 多边形(墙轮廓 / 房间 / 洞口,支持布尔运算)
  → 3D 建模(两条路线):
      A. SimpleCAD(OCCT)→ STEP(纯几何)
      B. IfcOpenShell     → IFC(几何 + BIM 语义)
```

## 2. SimpleCADAPI(本仓库)

- **定位**:基于 OCCT 的薄封装 Python CAD SDK,几何内核全部是 OCCT。
- **能力**:图元(box/cylinder/cone/polyline)、拉伸/旋转/放样/扫掠、布尔(union/cut/intersect,
  均保证返回单一 Solid)、抽壳、倒角、标签(tag)+ QL 查询、GraphSession 图记录、
  `export_model_json` / `replay_model_json` 可回放模型 JSON、`export_step` / `export_stl`。
- **不含**:DXF 导出(仅 STEP/STL)。
- **已验证产出**(`examples/` 下,全部通过图回放):
  - `21_rural_single_story_house.py` → 农村平房(空心墙 + 人字屋顶 + 门窗开洞)STEP/STL
  - `22_three_arch_bridge.py` → 三孔石拱桥 STEP
  - `23_greek_temple.py` → 帕特农式神殿 STEP
  - `24_commercial_ground_floor_dxf.py` → 商业楼一层平面图 DXF(用 ezdxf 生成,非 SDK 能力)
- **经验**:
  - union 要求真实体积重叠;贴合而非嵌入时需加大嵌入量(规则 16)。
  - 薄壳顶面与屋顶合并时默认 `glue=True` 会失败,`glue=False` 可正常合并。

## 3. cad-to-shapely

位置:`/CADapi/cad-to-shapely/`

- **核心**:`DxfImporter`(cad_to_shapely/dxf.py)用 ezdxf 解析
  `LINE / ARC / CIRCLE / POLYLINE / LWPOLYLINE / SPLINE`;
  弧按 `degrees_per_segment` 离散,bulge 弧、SPLINE(geomdl 采样)、OCS→WCS 镜像变换均已处理;
  输出 shapely `LineString` / `LinearRing`。
- **基类 `CadImporter`**:
  - `zip()`:端点吸附,自适应容差 `RELATIVE_ZIP_LENGTH = 1e-5`(按图幅缩放,解决 CAD 线微缝隙)。
  - `polygonize()`:基于 `shapely.ops.polygonize_full` 还原封闭多边形,失败时自动 zip 重试。
- **工具**:`utils.filter_polygons`(区分带孔面/孔环)、`point_in_polygon` 等。
- **设计场景**:型钢**封闭截面**(example_files 均为截面图),并非建筑平面图。
- **实测**(转换本研究生成的 36m×18m 商业楼 DXF):
  240 线 + 15 弧全部解析,bounds 正确;polygonize 得 27 个面但伴随 147 条 cuts ——
  双线墙 + 门窗洞口的建筑图需要在其输出之上再做图层过滤与墙体/洞口重构。
- **在流水线中的作用**:负责 DXF→shapely 的第一段;墙体重构、洞口还原逻辑需自研。

## 4. IfcOpenShell(v0.8.0,源码已下载至 /CADapi/IfcOpenShell)

- **开源**:https://github.com/IfcOpenShell/IfcOpenShell ,LGPL-3.0;文档 https://docs.ifcopenshell.org
- **与 cadquery 的异同**:同为 Python 代码建模、底层都依赖 OCCT;但 cadquery 产出无语义 B-rep,
  IfcOpenShell 产出带空间结构/类型/材质/属性集的完整 BIM 语义模型。

### 4.1 `src/` 子项目(36 个)

| 类别 | 模块 |
|---|---|
| 核心 | `ifcopenshell-python`、`ifcparse`、`ifcgeom`、`ifcwrap` |
| 转换 | `ifcconvert`、`serializers`(STEP/XML)、`ifccityjson`、`svgfill` |
| 分析校验 | `ifctester`(IDS)、`ifcclash`、`ifcdiff`、`ifcbimtester`、`ifcfm`、`ifcquery` |
| 流程 | `ifc4d`(进度)、`ifc5d`(造价)、`ifc2ca`、`ifccsv`、`bcf`、`bsdd`、`ifcpatch` |
| 应用 | `bonsai`(Blender BIM)、`qtviewer`、`ifcblender`、`ifcsverchok`、`ifcchat`、`ifcmcp` |

### 4.2 `ifcopenshell-python` API 结构

- **顶层**:`ifcopenshell.open()`(spf/xml/zip/sqlite/rocksdb)、`create_entity()`、`file.py`、`guid.py`、`validate.py`。
- **高层 API**(`ifcopenshell.api`,34 个领域包,统一 `ifcopenshell.api.run("<module>.<usecase>", file, ...)`):
  - 项目骨架:`project.create_file` → `root.create_entity` → `unit.assign_unit` →
    `spatial.assign_container`(Site→Building→Storey)→ `aggregate.assign_object`
  - 几何:`geometry.add_wall_representation` / `add_slab/window/door/railing_representation` /
    `add_profile_representation` / `add_mesh_representation` / `add_boolean` /
    `create_2pt_wall` / `connect_wall` / `edit_object_placement`
  - 洞口门窗:`feature.add_feature` + `feature.add_filling`
  - 轮廓:`profile.add_arbitrary_profile(_with_voids)` ← **直接承接 shapely 多边形**
  - 材质/样式:`material.add_layer`、`style.add_surface_style`
  - 语义:`pset.add_pset` / `edit_qto`、`classification`、`type.assign_type`
  - 其他:`grid`(轴网)、`drawing`(出图)、`structural`、`sequence`、`cost`
- **底层几何**:`util/shape_builder.py` 的 `ShapeBuilder`(numpy 级拉伸/扫掠工具);
  `geom/occ_utils.py` 与 OCCT 形状互转。

### 4.3 IFC 路线的成熟度结论

IFC authoring 有成熟方案(IfcOpenShell 即开源事实标准)。若终点是"带语义的 BIM 模型"
(墙/门窗/空间/属性可交换、可进 Revit/Bonsai),IFC 优于 STEP;若只要几何实体给结构/制造用,
STEP(SimpleCAD/OCCT)更轻。

## 5. 选型建议

| 需求终点 | 推荐路线 |
|---|---|
| 单层建筑几何实体(结构/可视化/加工) | DXF → cad-to-shapely → SimpleCAD 拉伸/布尔 → STEP |
| 带语义 BIM 模型(房间/门窗/材质/属性) | DXF → cad-to-shapely → IfcOpenShell api(profile→wall→feature→spatial)→ IFC |

**待自研的中间层**(两条路线共用):
1. DXF 图层语义约定(如 WALLS 双线墙、OPENINGS 洞口、COLUMNS 柱)。
2. shapely 层墙体重构:双线墙取轮廓、门窗断口还原为切割盒、房间多边形提取。
3. 单位与坐标对齐(DXF $INSUNITS → 模型单位)。

## 6. 产物清单

- `SimpleCADAPI/examples/21~24` 四个示例脚本及 `examples/out/` 下 STEP/STL/DXF/model JSON
- 本文档:`AI_IFC/research/ifc/README.md`
- `frontend_load.md` — IFC 网页显示/加载五条路线调研
- `MCP_API.md` — ifcmcp 与社区 MCP 调研
- `ifcopenshell-python/` — ifcopenshell-python 官方文档离线镜像(2026-07-23 扒取)
- `ifcopenshell_python_dev_notes.md` — **官方文档压缩版开发参考**(建模骨架/表示选型/selector/glTF 序列化/校验,skill 构建底稿)
- `simplecadapi_skill_anatomy.md` — **SimpleCADAPI skill 设计解剖**(模块拆分/知识串联机制/AI_IFC 复刻清单;含参考输入机制与 DXF/STEP 文件边界的源码实证)
