# Entities Index — 实体属性规格索引

> IFC 实体属性表(含继承, REQ/OPT/类型/声明类)。**可累加**: 新增实体加到对应分类文件。
> 数据源: `ifcopenshell.schema_by_name("IFC4")` 内省 + `doc.get_entity_doc()`(规范性)。
> 按类分文件, 本 README 只留索引(追踪轨迹)。

## 分类

- [spatial.md](spatial.md) — 空间结构: IfcProject / IfcSite / IfcBuilding / IfcBuildingStorey / IfcSpace
- [elements.md](elements.md) — 建筑元素: IfcWall / IfcDoor / IfcWindow / IfcSlab / IfcBeam / IfcColumn / IfcOpeningElement / IfcCurtainWall / IfcPlate / IfcMember / IfcCovering
- [geometry.md](geometry.md) — 几何图元: IfcExtrudedAreaSolid / IfcArbitraryClosedProfileDef / IfcLocalPlacement(placement 父子链)

## 用法

- 生成代码前查实体属性(REQ 必填 / PredefinedType 枚举), 配合 `../DESIGN_JSON_SCHEMA.md`(框定)与 `../psets/`(属性集)。
- PredefinedType 枚举值必须与表一致(7 层校验 #18, 见 SKILL.md)。

## Related

- `../psets/README.md` — 属性集(Pset/Qto)索引
- `../api/README.md` — ifcopenshell.api usecase 索引
- `../../ENTITY_SPECS.md` — 实体属性总索引(指向本目录)
