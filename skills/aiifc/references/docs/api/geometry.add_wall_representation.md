# geometry.add_wall_representation

## API Definition

```python
def add_wall_representation(model, context: entity_instance, length: float = 1.0, height: float = 3.0, direction_sense: str = POSITIVE, offset: float = 0.0, thickness: float = 0.2, x_angle: float = 0.0, clippings: Optional[list[Clipping | dict[str, Any]]], booleans: Optional[list[entity_instance]]) -> entity_instance
```

*Source: api/geometry/add_wall_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_wall_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_wall_representation(model, ...)`

## Description

Add a geometric representation for a wall.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext for the representation, only Model/Body/MODEL_VIEW type of representations are currently supported.
- **length** (`float`) , default: `1.0` : The length of the wall in meters.
- **height** (`float`) , default: `3.0` : The height of the wall in meters.
- **direction_sense** (`str`) , default: `POSITIVE`
- **offset** (`float`) , default: `0.0` : The base offset distance of the wall from the origin.
- **thickness** (`float`) , default: `0.2` : The thickness of the wall in meters.
- **x_angle** (`float`) , default: `0.0` : The slope angle along the wall's X-axis, in radians.
- **clippings** (`Optional[list[Clipping | dict[str, Any]]]`) : List of clipping definitions. Clippings can be `Clipping` objects or dictionaries of arguments for `Clipping.parse`. Each clipping has a ``normal`` that points toward the removed material (the discarded side), not toward the kept material; see :func:`clip_solid` for details.
- **booleans** (`Optional[list[entity_instance]]`) : List of any existing IfcBooleanResults.
## Returns

IfcShapeRepresentation.

## Known Pattern: box primitive for non-wall elements (verified, shopping_mall)

`add_wall_representation` produces a cuboid box — usable as geometry for many non-wall element types:

| Element | Box params | Placement note |
|---|---|---|
| **Beam (IfcBeam)** | `length`=span, `height`=beam depth (Z), `thickness`=beam width | `edit_object_placement` rotates so box X-axis aligns with beam axis, Y-axis = width direction |
| **Escalator slope (IfcStairFlight)** | `length`=sloped length (_hypot(run, rise)), `height`=deck thickness (0.15m), `thickness`=width (1.5m), `x_angle`=atan2(rise, run) | Box tilts about X; base edge aligned to elevation |
| **Column (IfcColumn)** | `length`=side, `height`=storey height, `thickness`=other side (equal for square) | Box base aligned to storey base elevation |

Ref: `AI_IFC/examples/shopping_mall.py` (264 beams + 168 columns + 6 escalator slopes all based on this usecase).
