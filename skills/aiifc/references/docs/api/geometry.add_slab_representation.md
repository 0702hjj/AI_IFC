# geometry.add_slab_representation

## API Definition

```python
def add_slab_representation(model, context: entity_instance, depth: float = 0.2, direction_sense: str = POSITIVE, offset: float = 0.0, x_angle: float = 0.0, clippings: Optional[list[Clipping | entity_instance]], polyline: Optional[list[tuple[float, float]]]) -> entity_instance
```

*Source: api/geometry/add_slab_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_slab_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_slab_representation(model, ...)`

## Description

Add a geometric representation for a slab.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext for the representation, only Model/Body/MODEL_VIEW type of representations are currently supported.
- **depth** (`float`) , default: `0.2` : The slab depth, in meters.
- **direction_sense** (`str`) , default: `POSITIVE`
- **offset** (`float`) , default: `0.0`
- **x_angle** (`float`) , default: `0.0` : The slope angle along the slab's X-axis, in radians.
- **clippings** (`Optional[list[Clipping | entity_instance]]`) : List of planes that define clipping half space solids. Clippings can be `Clipping` objects or dictionaries of arguments for `Clipping.parse`.
- **polyline** (`Optional[list[tuple[float, float]]]`)
## Returns

IfcShapeRepresentation.
