# ifcopenshell-python 开发参考(压缩版)

- 来源:<https://docs.ifcopenshell.org/ifcopenshell-python.html>(IfcOpenShell 0.8.5 官方文档)
- 整理日期:2026-07-23;离线镜像:`AI_IFC/research/ifc/ifcopenshell-python/`;rst 源:`IfcOpenShell/IfcOpenShell-0.8.0/src/ifcopenshell-python/docs/ifcopenshell-python/`(均相对工作区根)
- 用途:任务线 2 构建 `AI_IFC/skills/ai_ifc/` 的核心知识底稿;写建模脚本时先查此文,细节再回查镜像全文

---

## 1. 安装

```bash
pip install ifcopenshell          # 开发者首选(PyPI)
conda install -c ifcopenshell -c conda-forge ifcopenshell  # conda(附赠 IfcConvert)
docker run -it aecgeeks/ifcopenshell ...                    # Docker(附赠 IfcConvert)
```

- WASM 方案:pyodide wheels 在 `IfcOpenShell/wasm-wheels`;demo 在源码 `src/pyodide/demo-app/`(任务线 1 相关)
- 若与 pythonocc-core 同环境,需同环境一次装好让 conda 解出兼容的 occt 版本

## 2. 文件级操作(hello_world 精要)

```python
import ifcopenshell
model = ifcopenshell.open('model.ifc')   # 打开;model.schema → IFC2X3/IFC4/IFC4X3
model = ifcopenshell.file(schema='IFC4') # 从零创建(默认 IFC4)
model.by_id(1); model.by_guid('...'); model.by_type('IfcWall')
wall.is_a(); wall.is_a('IfcElement')     # 类判断(含父类)
wall[0]; wall.GlobalId; wall.get_info()  # 属性访问(索引/名称/全量 dict)
wall.Name = '...'; wall.GlobalId = ifcopenshell.guid.new()  # 修改直接赋值
model.get_inverse(wall); model.traverse(wall, max_levels=1) # 反向/正向引用
model.create_entity('IfcWall', GlobalId=ifcopenshell.guid.new(), Name='W')  # 关键词参数创建
new_model.add(wall)                      # 跨文件拷贝(递归,但不保证单位等一致性)
model.remove(wall); model.write('out.ifc')
```

常用 util:`ifcopenshell.util.element.get_psets(wall)`(属性+工程量 dict);`get_type/get_types`;`get_container/get_decomposition`;`ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)`(4x4 numpy 矩阵);`ifcopenshell.util.unit.calculate_unit_scale(model)`(项目单位→SI 米)。

## 3. 从零建模标准骨架(必背顺序)

**项目 → 单位 → 上下文 → 空间结构 → 元素 → 定位 → 表示 → 挂接**,对应官方 code_examples 的 "Create a simple model from scratch":

```python
import ifcopenshell.api.root, ifcopenshell.api.unit, ifcopenshell.api.context
import ifcopenshell.api.project, ifcopenshell.api.spatial, ifcopenshell.api.geometry
import ifcopenshell.api.aggregate

model = ifcopenshell.api.project.create_file()
project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="My Project")
ifcopenshell.api.unit.assign_unit(model)                       # 无参 = mm/m²/m³ 公制快捷
model3d = ifcopenshell.api.context.add_context(model, context_type="Model")
body = ifcopenshell.api.context.add_context(model, context_type="Model",
    context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)

site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="My Site")
building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="A")
storey = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="GF")
ifcopenshell.api.aggregate.assign_object(model, relating_object=project, products=[site])
ifcopenshell.api.aggregate.assign_object(model, relating_object=site, products=[building])
ifcopenshell.api.aggregate.assign_object(model, relating_object=building, products=[storey])

wall = ifcopenshell.api.root.create_entity(model, ifc_class="IfcWall")
ifcopenshell.api.geometry.edit_object_placement(model, product=wall)  # 默认原点
rep = ifcopenshell.api.geometry.add_wall_representation(model, context=body, length=5, height=3, thickness=0.2)
ifcopenshell.api.geometry.assign_representation(model, product=wall, representation=rep)
ifcopenshell.api.spatial.assign_container(model, relating_structure=storey, products=[wall])
model.write("model.ifc")
```

要点:

- **几何可选**,但有几何就必须有 ObjectPlacement;坐标全部用项目单位
- 单位可显式:`add_si_unit(model, unit_type="LENGTHUNIT", prefix="MILLI")` 再 `assign_unit(model, units=[length])`
- **Body 上下文每个项目只建一次,之后复用**;也可用 `ifcopenshell.util.representation.get_context(model, "Model", "Body", "MODEL_VIEW")` 取回
- 其他常用子上下文:Axis(GRAPH_VIEW,轴线参数化)、Box(MODEL_VIEW,碰撞/懒加载)、Plan/Annotation(PLAN_VIEW 等 2D 标注)

## 4. Object Placement(4x4 矩阵约定)

右手坐标系:X=项目东,Y=项目北,Z=向上(与 Blender 一致)。矩阵布局:

```
XAxis_X YAxis_X ZAxis_X X
XAxis_Y YAxis_Y ZAxis_Y Y
XAxis_Z YAxis_Z ZAxis_Z Z
0       0       0       1
```

```python
import numpy, ifcopenshell.util.placement
matrix = numpy.eye(4)
matrix = ifcopenshell.util.placement.rotation(90, "Z") @ matrix  # 先旋转(绕原点)
matrix[:,3][0:3] = (2, 3, 5)                                      # 后平移
ifcopenshell.api.geometry.edit_object_placement(model, product=wall, matrix=matrix, is_si=True)
# is_si=True 表示用 SI 米而非项目单位
# 移动装配体时:should_transform_children=True 子对象跟随;默认 False 只动父级(子级世界坐标不变)
```

## 5. Representation 技术选型

| 技术 | API | 适用 |
|---|---|---|
| Mesh(顶点/面,可带孔) | `geometry.add_mesh_representation(model, context=body, vertices=[[...]], faces=[[...]])` | 家具、幕墙三角面、异形近似体 |
| 墙状块(长/高/厚) | `geometry.add_wall_representation(..., length, height, thickness)`;两点墙:`geometry.create_2pt_wall(model, element, context, p1, p2, elevation, height, thickness)` | 墙、保温、均厚板;从 placement 沿局部 +X 生长,厚度沿 Y |
| 型材拉伸(2D 截面 +Z 拉伸) | `geometry.add_profile_representation(model, context=body, profile=..., depth=1)` | 板/柱/梁;梁需把 placement 放倒 |
| 自定义多实体组合 | `ShapeBuilder`(见 §6) | 桌子等组合体 |
| OCC 直转 | `ifcopenshell.geom.serialise("IFC4", occ_shape, False)` 再 `model.add(...)` | 已有 pythonOCC 形状;**IFC2X3 对曲面支持差,失败返回 None,优先 IFC4** |
| 手工逐实体 | `createIfcExtrudedAreaSolid` + `createIfcShapeRepresentation(ContextOfItems=body, RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[...])` | 教学/特殊形状,不推荐常规用 |

**参数化截面**(ProfileType="AREA",可给 ProfileName 复用):`IfcRectangleProfileDef(XDim, YDim)`、`IfcRoundedRectangleProfileDef(+RoundingRadius)`、`IfcRectangleHollowProfileDef(+WallThickness,...)`、`IfcCircleProfileDef(Radius)`、`IfcCircleHollowProfileDef`、`IfcEllipseProfileDef(SemiAxis1/2)`、`IfcIShapeProfileDef(OverallWidth, OverallDepth, WebThickness, FlangeThickness, FilletRadius?)`、L/T/U/Z/C 各 Shape。**钢截面优先用国标/标准命名**(如 "HEA100")。

**任意截面**(ShapeBuilder 三点弧,arc_points 从 1 计数;inner_curves 表孔):

```python
builder = ifcopenshell.util.shape_builder.ShapeBuilder(model)
outer = builder.polyline([(0.,0.),(100.,0.),(100.,50.),(51.2,98.7),(18.5,105.3),(0.,77.5)], arc_points=[4], closed=True)
inner = builder.circle((50.,50.), radius=10.)
profile = builder.profile(outer, inner_curves=[inner], name="Arbitrary")
```

## 6. ShapeBuilder 组合体(依赖 mathutils)

```python
from ifcopenshell.util.shape_builder import V
builder = ifcopenshell.util.shape_builder.ShapeBuilder(model)
rect = builder.rectangle(size=V(1200, 700))
top = builder.extrude(builder.profile(rect), 50, V(0, 0, 700))          # profile→拉伸(深,偏移)
legs = [c] + builder.mirror(c, mirror_axes=[V(1,0),V(0,1),V(1,1)], mirror_point=V(w/2,d/2), create_copy=True)
builder.translate(items, V(-w/2, -d/2).to_3d())                          # 平移对齐原点
body = ifcopenshell.util.representation.get_context(model, "Model", "Body", "MODEL_VIEW")
rep = builder.get_representation(context=body, items=items)
# 钢筋/栏杆:圆盘沿路径扫掠
swept = builder.create_swept_disk_solid(builder.polyline([...], arc_points=[2]), radius=10)
```

## 7. 类型 / 材质集(强烈建议先建 Type 再建实例)

- **Mapped Representation**:表示挂到 Type 上,实例 `type.assign_type(model, related_objects=[el], relating_type=type)` 后自动映射,无需逐实例建几何
- **IfcMaterialLayerSet**(墙等层状):`material.add_material_set(model, name=..., set_type="IfcMaterialLayerSet")` → `material.add_material(model, name=..., category=...)` → `material.add_layer(model, layer_set=..., material=...)` + `material.edit_layer(..., attributes={"LayerThickness": 13})` → `material.assign_material(model, products=[wall_type], material=set)`。**层厚之和必须等于墙体表示的 thickness,库不校验,自己保证**
- **IfcMaterialProfileSet**(梁柱等截面):`add_material_set(set_type="IfcMaterialProfileSet")` → `material.add_profile(model, profile_set=..., material=..., profile=hea100)` → assign 到 beam_type;实例表示**复用同一 profile** 拉伸

## 8. 洞口 / 裁剪(0.8.5 新增约定)

- 裁剪法线约定:`geometry.clip_solid(model, item=..., location=[...], normal=[...])` 的 normal **指向被移除的一侧**;裁剪后把 `RepresentationType` 改为 `"Clipping"`;`add_wall_representation` 的 `clippings` 参数同理
- 洞口生命周期:`feature.remove_feature(model, feature=opening)` 只删洞口,填充物(门窗)变孤儿,需先 `root.remove_product(model, product=window)`

## 9. 查询与接地(selector 语法,skill 的 QL 对应物)

```python
import ifcopenshell.util.selector
ifcopenshell.util.selector.filter_elements(model, "IfcWall, IfcSlab, material=concrete")
ifcopenshell.util.selector.get_element_value(wall, "type.Name")
```

- 过滤组语法:`filter[,filter]*` 组内从左到右链式,`+` 并集;`/* */` 注释;`!` 排除
- 过滤器:Class(`IfcWall`)、GlobalId 直写、属性(`Name=Foo`)、属性集(`Pset_WallCommon.FireRating=2HR`)、`type=`、`material=`、`classification=`、`location=`、`parent=`(均任意深度匹配)、`query:"parent.Name"="My Site"`(仅直接父级)
- 比较符:`= != > >= < <= *= !*=`;值三种写法:裸串 / `"带引号"` / `/正则/`
- 取值 key:`id class predefined_type <属性> <Pset>.<Prop> type types.count container space storey building site parent material material.item.0.Name materials.count x y z easting northing elevation rotation_x/y/z count <索引>`
- 格式化:`upper/lower/title/concat/round/int/number/metric_length/imperial_length/sort/reverse/join` 及四则运算,可嵌套

## 10. Schema 内省与 Pset 模板

```python
ifc4 = ifcopenshell.schema_by_name("IFC4")
d = ifc4.declaration_by_name("IfcWall")
d.is_abstract(); d.supertype(); d.subtypes(); d.attributes(); d.all_attributes(); d.all_inverse_attributes()

import ifcopenshell.util.pset
tpl = ifcopenshell.util.pset.PsetQto("IFC4")
tpl.get_applicable_names("IfcWall")   # ['Pset_WallCommon', 'Qto_WallBaseQuantities', ...]
tpl.get_by_name('Pset_WallCommon')    # IfcPropertySetTemplate
```

## 11. 几何处理(读取侧)

- 单元素:`ifcopenshell.geom.create_shape(settings, element, geometry_library="hybrid-cgal-simple-opencascade")`(推荐内核);取 `shape.geometry.verts/faces/edges`(扁平 list,faces 恒为三角形)、`shape.transformation.matrix`、`shape.geometry.materials/material_ids`
- numpy 化:`util.shape.get_vertices/get_edges/get_faces/get_shape_matrix`
- 也可传 representation / representation item / profile(此时直接返回 geometry);元素多 Body 表示时第三参指定
- **批量一律用迭代器**(多核+缓存):

```python
iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count(),
    include=walls, geometry_library="hybrid-cgal-simple-opencascade")
if iterator.initialize():
    while True:
        shape = iterator.get()
        ...
        if not iterator.next(): break
```

- OCC BRep:`settings.set("use-python-opencascade", True)`
- 手工解析:记得 `util.unit.calculate_unit_scale(ifc_file)` 换 SI

## 12. 序列化输出(任务线 1 预转换路线实操参数)

```python
settings = ifcopenshell.geom.settings()
settings.set("dimensionality", ifcopenshell.ifcopenshell_wrapper.CURVES_SURFACES_AND_SOLIDS)
settings.set("apply-default-materials", True)          # glTF 必须
ss = ifcopenshell.geom.serializer_settings()
ss.set("use-element-guids", True)                      # 非语义格式里保留对象标识
ser = ifcopenshell.geom.serializers.gltf("output.glb", settings, ss)
ser.setFile(ifc_file); ser.setUnitNameAndMagnitude("METER", 1.0); ser.writeHeader()
# 配 §11 迭代器逐个 ser.write(iterator.get()),最后 ser.finalize()
# OBJ:serializers.obj('out.obj','out.mtl',...),另加 settings.set("use-world-coords", True)
```

## 13. 校验(端到端验证的接地手段)

```bash
python -m ifcopenshell.simple_spf model.ifc            # SPF 语法级校验,--json 可机器读
python -m ifcopenshell.validate model.ifc --rules      # schema 级校验(属性/类型/基数/where 规则)
                                                       # --json / --fields / --spf 控制输出
```

skill 的最小端到端脚本即以 `ifcopenshell.validate` 通过为验收标准。

## 14. 几何树(碰撞/选择,后续扩展用)

- `ifcopenshell.geom.tree()` + 迭代器 `add_element`(三角面→BVH 树:碰撞;`add_element(iterator.get_native())`→UB 树:选择)
- 碰撞:`clash_intersection_many(a, b, tolerance=0.002, check_all=True)`(突出/贯穿,推荐非零 tolerance)、`clash_collision_many(..., allow_touching=True)`(最快,仅表面)、`clash_clearance_many(..., clearance=0.1)`(净距)
- 选择:`select_box` / `select` / `select_ray(origin, dir, length)`(**坐标一律 SI 米**)

---

## 与流水线的映射(DXF→shapely→IFC)

1. cad-to-shapely 的多边形 → §5 任意截面(`builder.polyline(...)`)或手工 `IfcArbitraryClosedProfileDef`
2. 墙体 → `create_2pt_wall`(DXF 双线/中心线 + 层高);板 → 轮廓 + `add_profile_representation`
3. 每步后 §9 selector / ifcquery 打印接地事实;终验 §13 validate
4. 出图展示 → §12 glb 序列化 → 前端 three.js/xeokit(见 `frontend_load.md`)
