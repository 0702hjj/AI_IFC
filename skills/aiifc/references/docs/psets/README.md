# Psets Index — 属性集索引

> 各实体的适用 Pset/Qto + 属性清单。**可累加**: 新增实体 Pset 加到对应分类文件。
> 数据源: `ifcopenshell.util.pset.PsetQto("IFC4")` + `doc.get_property_set_doc()`(规范性)。
> 按类分文件, 本 README 只留索引(追踪轨迹)。

## 分类

- [walls_openings.md](walls_openings.md) — 墙与门窗: IfcWall(Pset_WallCommon) / IfcDoor / IfcWindow
- [slabs_roof.md](slabs_roof.md) — 板与屋顶覆盖: IfcSlab(PitchAngle) / IfcRoof / IfcCovering(ROOFING 瓦·金属) / IfcChimney
- [structure_circulation.md](structure_circulation.md) — 结构与流线: IfcBeam(屋架) / IfcColumn / IfcStairFlight / IfcRailing
- [common_usage.md](common_usage.md) — 通用 Pset + 使用规则 + 打标经验(每类 pset+material 不漏)

## 用法

- 挂 pset 前查对应实体文件确认适用集 + 属性名(7 层校验 #4/#17, 见 SKILL.md)。
- 数值属性单位: 多数用项目单位 mm(见各文件标注)。

## Related

- `../entities/README.md` — 实体属性规格索引
- `../../PSET_REFERENCE.md` — 属性集总索引(指向本目录)
