# Entity Specs — 实体属性规格索引

> 实体属性表(含继承, REQ/OPT/类型/声明类)已**归档到 `docs/entities/`**(按类分文件 + 索引),本文件只留总索引(追踪轨迹)。
> 数据源: `ifcopenshell.schema_by_name("IFC4")` 内省 + `doc.get_entity_doc()`(规范性, 7 层校验 #18)。

## 索引 → `docs/entities/README.md`

- [spatial.md](docs/entities/spatial.md) — 空间结构: IfcProject / IfcSite / IfcBuilding / IfcBuildingStorey / IfcSpace
- [elements.md](docs/entities/elements.md) — 建筑元素: IfcWall / IfcDoor / IfcWindow / IfcSlab / IfcBeam / IfcColumn / IfcOpeningElement / IfcCurtainWall / IfcPlate / IfcMember / **IfcCovering**(屋面覆盖)
- [geometry.md](docs/entities/geometry.md) — 几何图元: IfcExtrudedAreaSolid / IfcArbitraryClosedProfileDef / IfcLocalPlacement(placement 父子链)

## 用法

- 生成代码前查实体属性: **REQ 必填**(GlobalId 等)、**PredefinedType 枚举值**必须与表一致。
- PredefinedType 校验: 值必须在实体枚举列表内(SKILL.md MUST #16)。
- 配合 `PSET_REFERENCE.md`(→ `docs/psets/`)挂属性集, `DESIGN_JSON_SCHEMA.md`(→ design JSON)框定几何。
