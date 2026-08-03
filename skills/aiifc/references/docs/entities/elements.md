# Building Element Entities(建筑元素实体)

> 从 ENTITY_SPECS 归档: 建筑构件实体(墙/门窗/板/梁柱/覆盖层等)。1-8 同 IfcWall(GlobalId/OwnerHistory/Name/Description/ObjectType/ObjectPlacement/Representation/Tag),仅列差异。

### IfcWall (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1-8 | (base: GlobalId/OwnerHistory/Name/Description/ObjectType/ObjectPlacement/Representation/Tag) | | | |
| 9 | **PredefinedType** | OPT | IfcWallTypeEnum | IfcWall |

PredefinedType: ELEMENTEDWALL / MOVABLE / NOTDEFINED / PARAPET / PARTITIONING / PLUMBINGWALL / POLYGONAL / SHEAR / SOLIDWALL / STANDARD / USERDEFINED

### IfcDoor (13 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | **OverallHeight** | OPT | IfcPositiveLengthMeasure | IfcDoor |
| 10 | **OverallWidth** | OPT | IfcPositiveLengthMeasure | IfcDoor |
| 11 | PredefinedType | OPT | IfcDoorTypeEnum | IfcDoor |
| 12 | OperationType | OPT | IfcDoorTypeOperationEnum | IfcDoor |
| 13 | UserDefinedOperationType | OPT | IfcLabel | IfcDoor |

PredefinedType: DOOR / GATE / NOTDEFINED / TRAPDOOR / USERDEFINED

### IfcWindow (13 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | **OverallHeight** | OPT | IfcPositiveLengthMeasure | IfcWindow |
| 10 | **OverallWidth** | OPT | IfcPositiveLengthMeasure | IfcWindow |
| 11 | PredefinedType | OPT | IfcWindowTypeEnum | IfcWindow |
| 12 | PartitioningType | OPT | IfcWindowTypePartitioningEnum | IfcWindow |
| 13 | UserDefinedPartitioningType | OPT | IfcLabel | IfcWindow |

PredefinedType: LIGHTDOME / NOTDEFINED / SKYLIGHT / USERDEFINED / WINDOW

### IfcSlab (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | **PredefinedType** | OPT | IfcSlabTypeEnum | IfcSlab |

PredefinedType: BASESLAB / FLOOR / LANDING / NOTDEFINED / **ROOF** / USERDEFINED

### IfcBeam (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcBeamTypeEnum | IfcBeam |

PredefinedType: BEAM / HOLLOWCORE / LINTEL / NOTDEFINED / SPANDREL / T_BEAM / USERDEFINED

> 屋架(steel half-truss)用 IfcBeam,见 design/roof_pitched。

### IfcColumn (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcColumnTypeEnum | IfcColumn |

PredefinedType: COLUMN / PILASTER / USERDEFINED / NOTDEFINED

### IfcOpeningElement (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcOpeningElementTypeEnum | IfcOpeningElement |

PredefinedType: NOTDEFINED / OPENING / RECESS / USERDEFINED

### IfcCurtainWall (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcCurtainWallTypeEnum | IfcCurtainWall |

PredefinedType(IFC4): NOTDEFINED / USERDEFINED

### IfcPlate (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcPlateTypeEnum | IfcPlate |

PredefinedType: CURTAIN_PANEL / NOTDEFINED / SHEET / USERDEFINED

### IfcMember (9 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | PredefinedType | OPT | IfcMemberTypeEnum | IfcMember |

PredefinedType: BRACE / CHORD / COLLAR / MEMBER / MULLION / PLATE / POST / PURLIN / RAFTER / STRINGER / STRUT / STUD / USERDEFINED / NOTDEFINED

### IfcCovering (9 attrs) — 覆盖层(屋面瓦/金属/保温/吊顶)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 9 | **PredefinedType** | OPT | IfcCoveringTypeEnum | IfcCovering |

PredefinedType: CEILING(吊顶) / CLADDING(幕墙覆面) / FLOORING(地面) / INSULATION(保温) / MEMBRANE(膜) / MOLDING(线脚) / NOTDEFINED / ROOFING(屋面) / SKIRTINGBOARD(踢脚) / SLEEVING(套管) / USERDEFINED / WRAPPING(包裹)

> 屋顶覆盖层(design/roof_pitched, Castle 逆向): 瓦片 dakpan=ROOFING, 金属屋面 zinkwerk=ROOFING, 滴水 waterslag=ROOFING/MOLDING, 保温 dakisolatie=INSULATION, 凸起 dakopstand=ROOFING。覆盖在 IfcSlab(PredefinedType=ROOF) 结构板上(**不用 IfcRoof**,真实 Revit 导出模型惯用 Slab+Covering 分层)。
