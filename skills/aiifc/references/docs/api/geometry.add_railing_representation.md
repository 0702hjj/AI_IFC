# geometry.add_railing_representation

## API Definition

```python
def add_railing_representation(model, context: entity_instance, railing_type: Literal['WALL_MOUNTED_HANDRAIL'] = WALL_MOUNTED_HANDRAIL, railing_path: Sequence[Any] | ndarray, use_manual_supports: bool = False, support_spacing: Optional[float], railing_diameter: Optional[float], clear_width: Optional[float], terminal_type: Literal['180', 'TO_END_POST', 'TO_WALL', 'TO_FLOOR', 'TO_END_POST_AND_FLOOR'] = 180, height: Optional[float], looped_path: bool = False, unit_scale: Optional[float]) -> entity_instance
```

*Source: api/geometry/add_railing_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_railing_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_railing_representation(model, ...)`

## Description

Units are expected to be in IFC project units.

## Parameters

- **context** (`entity_instance`) : IfcGeometricRepresentationContext for the representation.
- **railing_type** (`Literal['WALL_MOUNTED_HANDRAIL']`) , default: `WALL_MOUNTED_HANDRAIL` : Type of the railing. Defaults to "WALL_MOUNTED_HANDRAIL".
- **railing_path** (`Sequence[Any] | ndarray`) : A list of points coordinates for the railing path, coordinates are expected to be at the top of the railing, not at the center. If not provided, default path [(0, 0, 1), (1, 0, 1), (2, 0, 1)] (in meters) will be used
- **use_manual_supports** (`bool`) , default: `False` : If enabled, supports are added on every vertex on the edges of the railing path. If disabled, supports are added automatically based on the support spacing. Default to False.
- **support_spacing** (`Optional[float]`) : Distance between supports if automatic supports are used. Defaults to 1m.
- **railing_diameter** (`Optional[float]`) : Railing diameter. Defaults to 50mm.
- **clear_width** (`Optional[float]`) : Clear width between the railing and the wall. Defaults to 40mm.
- **terminal_type** (`Literal['180', 'TO_END_POST', 'TO_WALL', 'TO_FLOOR', 'TO_END_POST_AND_FLOOR']`) , default: `180` : type of the cap. Defaults to "180".
- **height** (`Optional[float]`) : defaults to 1m
- **looped_path** (`bool`) , default: `False` : Whether to end the railing on the first point of `railing_path`. Defaults to False.
- **unit_scale** (`Optional[float]`) : The unit scale as calculated by ifcopenshell.util.unit.calculate_unit_scale. If not provided, it will be automatically calculated for you.
## Returns

IfcShapeRepresentation for a railing.

## Known Issue: Missing default params trigger AttributeError (ifcopenshell 0.8.5)

Omitting any default-valued parameter (`support_spacing` / `railing_diameter` / `clear_width` / `height`) causes:

```
AttributeError: 'Usecase' object has no attribute 'settings'
```

Root cause: the module-level wrapper calls `usecase.convert_si_to_unit(...)` to compute defaults before `Usecase.settings` is injected.

**Workaround: pass all optional parameters explicitly** (project units, mm):

```python
ifcopenshell.api.run("geometry.add_railing_representation", model,
    context=body, railing_path=np.array([[0, 0, 1100], [12000, 0, 1100]]),  # mm
    height=1100, support_spacing=1000, railing_diameter=50, clear_width=40,
    unit_scale=ifcopenshell.util.unit.calculate_unit_scale(model))
```
