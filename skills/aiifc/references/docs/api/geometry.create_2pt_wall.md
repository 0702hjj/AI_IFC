# geometry.create_2pt_wall

## API Definition

```python
def create_2pt_wall(model, element: entity_instance, context: entity_instance, p1: tuple[float, float], p2: tuple[float, float], elevation: float, height: float, thickness: float, is_si: bool = True) -> entity_instance
```

*Source: api/geometry/create_2pt_wall*

## Import Surface

- run: `ifcopenshell.api.run("geometry.create_2pt_wall", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.create_2pt_wall(model, ...)`

## Description

Create a wall between two points (p1 and p2).

## Parameters

- **element** (`entity_instance`) : Wall IFC element.
- **context** (`entity_instance`) : IfcGeometricRepresentationContext for the representation. only Model/Body/MODEL_VIEW type of representations are currently supported.
- **p1** (`tuple[float, float]`) : The starting point (x, y) of the wall.
- **p2** (`tuple[float, float]`) : The ending point (x, y) of the wall.
- **elevation** (`float`) : The base elevation (z-coordinate) for the wall.
- **height** (`float`) : The height of the wall.
- **thickness** (`float`) : The thickness of the wall.
- **is_si** (`bool`) , default: `True` : If True, provided arguments units are treated as SI (meters). If False, values are converted from project units to SI.
## Returns

IfcShapeRepresentation.

## Known Behavior: elevation is World Coordinates (ifcopenshell 0.8.x)

`p1` / `p2` / `elevation` all use **world coordinates**. If the wall is later assigned to a storey with elevation (e.g. floor 2 at z=3.3m), the usecase writes compensating values into the wall's `RelativePlacement` (e.g. -3300mm), preserving the world position specified by `elevation`.

**Multi-storey walls require world elevation**: floor-2 walls need `elevation=3.3m` — never pass `elevation=0` expecting "storey-local" coords. Passing 0 causes floor-2 walls to overlap ground-floor walls at z=0.

Verification: `tracker.snapshot()` → read `world_xyz_mm`; each storey's walls should report z = 0 / 3300 / ...
