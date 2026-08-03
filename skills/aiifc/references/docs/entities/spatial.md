# Spatial Structure Entities(空间结构实体)

> 从 ENTITY_SPECS 归档: 空间树骨架实体。属性表含继承,标 REQ/OPT/类型/声明类。

### IfcProject (9 attrs)

The mandatory root. Exactly one per IFC file.

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | GlobalId | REQ | IfcGloballyUniqueId | IfcRoot |
| 2 | OwnerHistory | OPT | IfcOwnerHistory | IfcRoot |
| 3 | Name | OPT | IfcLabel | IfcRoot |
| 4 | Description | OPT | IfcText | IfcRoot |
| 5 | ObjectType | OPT | IfcLabel | IfcContext |
| 6 | LongName | OPT | IfcLabel | IfcContext |
| 7 | Phase | OPT | IfcLabel | IfcContext |
| 8 | RepresentationContexts | OPT | (set) | IfcContext |
| 9 | UnitsInContext | OPT | IfcUnitAssignment | IfcContext |

### IfcSite (14 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | GlobalId | REQ | IfcGloballyUniqueId | IfcRoot |
| 2 | OwnerHistory | OPT | IfcOwnerHistory | IfcRoot |
| 3 | Name | OPT | IfcLabel | IfcRoot |
| 4 | Description | OPT | IfcText | IfcRoot |
| 5 | ObjectType | OPT | IfcLabel | IfcObject |
| 6 | ObjectPlacement | OPT | IfcObjectPlacement | IfcProduct |
| 7 | Representation | OPT | IfcProductRepresentation | IfcProduct |
| 8 | LongName | OPT | IfcLabel | IfcSpatialElement |
| 9 | CompositionType | OPT | IfcElementCompositionEnum | IfcSpatialStructureElement |
| 10 | RefLatitude | OPT | IfcCompoundPlaneAngleMeasure | IfcSite |
| 11 | RefLongitude | OPT | IfcCompoundPlaneAngleMeasure | IfcSite |
| 12 | RefElevation | OPT | IfcLengthMeasure | IfcSite |
| 13 | LandTitleNumber | OPT | IfcLabel | IfcSite |
| 14 | SiteAddress | OPT | IfcPostalAddress | IfcSite |

### IfcBuilding (12 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | GlobalId | REQ | IfcGloballyUniqueId | IfcRoot |
| 2 | OwnerHistory | OPT | IfcOwnerHistory | IfcRoot |
| 3 | Name | OPT | IfcLabel | IfcRoot |
| 4 | Description | OPT | IfcText | IfcRoot |
| 5 | ObjectType | OPT | IfcLabel | IfcObject |
| 6 | ObjectPlacement | OPT | IfcObjectPlacement | IfcProduct |
| 7 | Representation | OPT | IfcProductRepresentation | IfcProduct |
| 8 | LongName | OPT | IfcLabel | IfcSpatialElement |
| 9 | CompositionType | OPT | IfcElementCompositionEnum | IfcSpatialStructureElement |
| 10 | ElevationOfRefHeight | OPT | IfcLengthMeasure | IfcBuilding |
| 11 | ElevationOfTerrain | OPT | IfcLengthMeasure | IfcBuilding |
| 12 | BuildingAddress | OPT | IfcPostalAddress | IfcBuilding |

### IfcBuildingStorey (10 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1-8 | (same as IfcBuilding 1-8) | | | |
| 9 | CompositionType | OPT | IfcElementCompositionEnum | IfcSpatialStructureElement |
| 10 | **Elevation** | OPT | IfcLengthMeasure | IfcBuildingStorey |

> Elevation is the storey height. Must be set during the skeleton (Wrapping) phase.

### IfcSpace (11 attrs)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1-9 | (same as IfcBuildingStorey 1-9) | | | |
| 10 | PredefinedType | OPT | IfcSpaceTypeEnum | IfcSpace |
| 11 | ElevationWithFlooring | OPT | IfcLengthMeasure | IfcSpace |

PredefinedType: EXTERNAL / GFA / INTERNAL / NOTDEFINED / PARKING / SPACE / USERDEFINED
