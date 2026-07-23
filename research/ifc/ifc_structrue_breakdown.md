# IFC 结构拆解与最小骨架计划

- 日期:2026-07-23
- 样本:`AI_IFC/research/ifc/Sample-Test-Files-main/IFC 4.3.2.0 (IFC4X3_ADD2)/PCERT-Sample-Scene/Building-Architecture.ifc`(SketchUp 导出独栋住宅,391 行,60+ 实体类型)
- 目的:为 AI_IFC skill 定义"AI 先生成结构骨架、细节后续填充"的建模策略

---

## 1. 完整 IFC 的 11 个逻辑层

```text
① 文件元数据层   HEADER(FILE_DESCRIPTION/FILE_NAME/FILE_SCHEMA) + OWNERHISTORY + PERSON/ORG/APPLICATION
② 项目与单位层   IfcProject(唯一根) + IfcUnitAssignment{IfcSIUnit:长度/面积/体积}
                  + IfcGeometricRepresentationContext(Model) + SubContext(Body/MODEL_VIEW)
③ 地理参考层     IfcProjectedCRS(EPSG) + IfcMapConversion(工程坐标↔地图坐标)
④ 空间结构层     IfcSite→IfcBuilding→IfcBuildingStorey(IfcRelAggregates 逐级嵌套)
                  + IfcSpace/IfcZone + IfcRelContainedInSpatialStructure + IfcRelAssignsToGroup
⑤ 类型层         IfcWallType/SlabType/... + IfcRelDefinesByType(实例→类型)
⑥ 构件实例层     IfcSlab/IfcWall/IfcRoof/IfcFurniture/IfcBuildingElementProxy/IfcEarthworksFill
⑦ 定位层         IfcLocalPlacement(父子嵌套) + IfcAxis2Placement3D + IfcCartesianPoint + IfcDirection
⑧ 几何表示层     IfcProductDefinitionShape→IfcShapeRepresentation
                  ├─ Tessellation:IfcTriangulatedFaceSet + IfcCartesianPointList3D(复杂体)
                  └─ SweptSolid:IfcExtrudedAreaSolid + IfcArbitraryClosedProfileDef + IfcPolyline(简单拉伸)
⑨ 材质与样式层   IfcMaterial + IfcRelAssociatesMaterial + IfcSurfaceStyle + IfcColourRgb + IfcStyledItem
⑩ 属性与工程量层 IfcPropertySet + IfcPropertySingleValue + IfcElementQuantity + IfcQuantity* + IfcRelDefinesByProperties
⑪ 分类层         IfcClassification + IfcClassificationReference + IfcRelAssociatesClassification
```

核心组织逻辑:**实体是名词,`IfcRel*` 是动词**,所有连接靠 7 种关系实体(Aggregates/ContainedInSpatialStructure/DefinesByType/DefinesByProperties/AssociatesMaterial/AssociatesClassification/AssignsToGroup）完成——IFC 解耦靠关系,不靠外键。

---

## 2. 最小骨架计划:AI 先生成结构,细节后续填

### 2.1 判断标准

**保留"结构与身份"层,去掉"数据与外观"层。** 判断依据是该层是否影响 IFC 合法性与结构完整性。

### 2.2 可去掉的 5 层(细节,后续填)

| 去掉的层 | 理由 | 合法性 |
|---|---|---|
| ③ 地理参考层 | 工程测量/GIS 才需要 | ✅ 合法 |
| ⑧ 几何表示层 | **IFC 官方明确几何可选**;设施管理/纯语义模型都不带几何 | ✅ 合法(产品可无表示) |
| ⑨ 材质与样式层 | 属于"上色",建架子阶段不必 | ✅ 合法 |
| ⑩ 属性与工程量层 | 数据,后续逐项挂 | ✅ 合法 |
| ⑪ 分类层 | 元数据,最后挂 | ✅ 合法 |

### 2.3 必须保留的 6 层(结构骨架)

```
① 文件元数据  HEADER(3 段)必须;OwnerHistory 可简化或省(IFC4 不强制)
② 项目+单位   IfcProject 是唯一强制根;单位——无几何时可极简,
              若后续要坐标建议至少留 LENGTHUNIT
④ 空间结构    Project→Site→Building→Storey 的 IfcRelAggregates 链
              (构件后续要装进来,容器层级先搭好)
⑤ 类型        可选但建议留——给后续实例一个"挂点"(Type 先行,实例映射)
⑥ 构件实例    可留空壳(仅 GlobalId/Name/ObjectType,无几何)——"框架"的本体
⑦ 定位        可暂时全用 identity placement(原点),后续再摆位
```

### 2.4 关键推论:去 ⑧ 会连带简化 ②⑦

去掉几何(⑧）后:

- **② 的 GeometricRepresentationContext/SubContext 也可去掉**(没有 Body 表示就不需要上下文）
- **⑦ 的 LocalPlacement 可全退化成 identity**(原点无旋转),甚至空间元素先不挂 placement 也合法

### 2.5 最小骨架形态

```
IfcProject
 └─(RelAggregates)→ IfcSite
                    └─(RelAggregates)→ IfcBuilding
                       └─(RelAggregates)→ IfcBuildingStorey
                          └─(RelContainedInSpatialStructure)→ [后续填构件]

IfcWallType "WAL01" ─(RelDefinesByType)→ [后续填 IfcWall 实例]
```

特征:**纯语义树**——项目→空间层级→类型→元素空壳(带 GlobalId 和名字,无几何/材质/属性),体积最小、生成最快。

### 2.6 后续填充路径(每加一类构件)

```
1. 建实例 IfcWall(GlobalId, Name, ObjectType)
2. RelDefinesByType      挂类型
3. RelContainedInSpatialStructure  装进楼层
4. edit_object_placement + assign_representation  补几何(可选)
5. material.assign_material                         补材质(可选)
6. pset.add_pset                                    补属性(可选)
```

每一步都是**纯增量插入,不破坏既有结构**——这是"骨架优先"策略的核心价值。

### 2.7 验收标准

最小骨架生成后必须通过:
```bash
python -m ifcopenshell.validate skeleton.ifc
```
即 IfcProject 存在、空间层级关系合法、无悬空引用。这是 ai_ifc skill 端到端验证的第一道关卡。
