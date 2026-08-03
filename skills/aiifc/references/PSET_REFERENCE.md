# Pset Reference — 属性集索引

> 各实体适用 Pset/Qto + 属性清单已**归档到 `docs/psets/`**(按类分文件 + 索引),本文件只留总索引(追踪轨迹)。
> 数据源: `PsetQto("IFC4")` + `doc.get_property_set_doc()`(规范性, 7 层校验 #4/#17)。

## 索引 → `docs/psets/README.md`

- [walls_openings.md](docs/psets/walls_openings.md) — 墙与门窗: IfcWall(Pset_WallCommon) / IfcDoor / IfcWindow
- [slabs_roof.md](docs/psets/slabs_roof.md) — 板与屋顶覆盖: IfcSlab(**PitchAngle**) / IfcRoof / **IfcCovering**(ROOFING 瓦·金属) / IfcChimney
- [structure_circulation.md](docs/psets/structure_circulation.md) — 结构与流线: IfcBeam(屋架) / IfcColumn / IfcStairFlight / IfcRailing
- [common_usage.md](docs/psets/common_usage.md) — 通用 Pset + 使用规则 + 打标经验(每类 pset+material 不漏)

## 用法

- 挂 pset 前: `PsetQto.get_applicable_names(class)` 验证适用性(防乱挂)。
- 填属性前: `doc.get_property_set_doc(pset)` 验证属性名与 schema 一致(防拼错)。
- 真实文件只用属性子集; Pset=设计师指定, Qto=几何派生。
