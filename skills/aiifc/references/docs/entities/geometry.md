# Geometry Primitives(几何图元)

> 从 ENTITY_SPECS 归档: 几何表示相关图元。

### IfcExtrudedAreaSolid (4 attrs) — swept solid (walls, slabs, beams, columns)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | **SweptArea** | REQ | IfcProfileDef | IfcSweptAreaSolid |
| 2 | Position | OPT | IfcAxis2Placement3D | IfcSweptAreaSolid |
| 3 | **ExtrudedDirection** | REQ | IfcDirection | IfcExtrudedAreaSolid |
| 4 | **Depth** | REQ | IfcPositiveLengthMeasure | IfcExtrudedAreaSolid |

### IfcArbitraryClosedProfileDef (3 attrs) — arbitrary closed profile (from coordinates/shapely)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | **ProfileType** | REQ | IfcProfileTypeEnum | IfcProfileDef |
| 2 | ProfileName | OPT | IfcLabel | IfcProfileDef |
| 3 | **OuterCurve** | REQ | IfcCurve | IfcArbitraryClosedProfileDef |

ProfileType: .CURVE. / .AREA.

### IfcLocalPlacement (2 attrs) — placement (parent-child chain)

| # | attr_name | opt | type | source |
|---|---|---|---|---|
| 1 | PlacementRelTo | OPT | IfcObjectPlacement | IfcLocalPlacement |
| 2 | **RelativePlacement** | REQ | IfcAxis2Placement | IfcLocalPlacement |

**PlacementRelTo determines the coordinate reference frame:**
- `PlacementRelTo = None` (or omitted): world coordinates
- `PlacementRelTo = host wall ObjectPlacement`: relative to host wall local coordinates
- `feature.add_feature` automatically sets the opening's PlacementRelTo to the host wall and converts the matrix from world to wall-relative (subtracting wall origin)
- `feature.add_filling` does NOT change the door/window PlacementRelTo

**Parent chain (bottom-up):**
```
Storey.ObjectPlacement     (elevation, e.g. 0m)
  └─ Building.ObjectPlacement    (relative to Storey)
     └─ Site.ObjectPlacement        (relative to Building)
        └─ (wall/door/window/slab).ObjectPlacement  (relative to container Storey)
           └─ (opening).ObjectPlacement              (relative to host wall, auto-set by add_feature)
```

**RelativePlacement is a 4×4 transform matrix:**
- Position (x, y, z) + rotation (XAxis, YAxis, ZAxis)
- Absolute coordinates = product of parent chain matrices: Storey_matrix @ Building_matrix @ Site_matrix @ element_matrix
