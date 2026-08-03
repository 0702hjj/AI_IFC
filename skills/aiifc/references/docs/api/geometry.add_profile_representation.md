# geometry.add_profile_representation

## API Definition

```python
def add_profile_representation(model, context: entity_instance, profile: entity_instance, depth: float = 1.0, cardinal_point: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19] | Literal['bottom left', 'bottom centre', 'bottom right', 'mid-depth left', 'mid-depth centre', 'mid-depth right', 'top left', 'top centre', 'top right', 'geometric centroid', 'bottom in line with the geometric centroid', 'left in line with the geometric centroid', 'right in line with the geometric centroid', 'top in line with the geometric centroid', 'shear centre', 'bottom in line with the shear centre', 'left in line with the shear centre', 'right in line with the shear centre', 'top in line with the shear centre'] | None = 5, clippings: Optional[list[Clipping | dict[str, Any]]], placement_zx_axes: tuple[Optional[tuple[float, float, float]], Optional[tuple[float, float, float]]] = (None, None)) -> entity_instance
```

*Source: api/geometry/add_profile_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_profile_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_profile_representation(model, ...)`

## Description

Add profile representation.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext for the representation, only Model/Body/MODEL_VIEW type of representations are currently supported.
- **profile** (`entity_instance`) : The IfcProfileDef to extrude.
- **depth** (`float`) , default: `1.0` : The depth of the extrusion in meters.
- **cardinal_point** (`Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19] | Literal['bottom left', 'bottom centre', 'bottom right', 'mid-depth left', 'mid-depth centre', 'mid-depth right', 'top left', 'top centre', 'top right', 'geometric centroid', 'bottom in line with the geometric centroid', 'left in line with the geometric centroid', 'right in line with the geometric centroid', 'top in line with the geometric centroid', 'shear centre', 'bottom in line with the shear centre', 'left in line with the shear centre', 'right in line with the shear centre', 'top in line with the shear centre'] | None`) , default: `5` : The cardinal point of the profile.
- **clippings** (`Optional[list[Clipping | dict[str, Any]]]`) : A list of planes that define clipping half space solids. Planes are defined either by Clipping objects or by dictionaries of arguments for `Clipping.parse`.
- **placement_zx_axes** (`tuple[Optional[tuple[float, float, float]], Optional[tuple[float, float, float]]]`) , default: `(None, None)` : A tuple of two vectors that define the placement of the profile. The first vector is the Z axis, the second vector is the X axis.
## Returns

IfcShapeRepresentation.
