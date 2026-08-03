# geometry.add_door_representation

## API Definition

```python
def add_door_representation(model, context: entity_instance, overall_height: Optional[float], overall_width: Optional[float], operation_type: Literal['SINGLE_SWING_LEFT', 'SINGLE_SWING_RIGHT', 'DOUBLE_SWING_RIGHT', 'DOUBLE_SWING_LEFT', 'DOUBLE_DOOR_SINGLE_SWING', 'DOUBLE_DOOR_DOUBLE_SWING', 'SLIDING_TO_LEFT', 'SLIDING_TO_RIGHT', 'DOUBLE_DOOR_SLIDING'] = SINGLE_SWING_LEFT, lining_properties: DoorLiningProperties | dict[str, Any] | None, panel_properties: DoorPanelProperties | dict[str, Any] | None, part_of_product: Optional[entity_instance], unit_scale: Optional[float]) -> Optional[entity_instance]
```

*Source: api/geometry/add_door_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_door_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_door_representation(model, ...)`

## Description

Add a geometric representation for a door.

units in usecase_settings expected to be in ifc project units

## Parameters

- **context** (`entity_instance`) : IfcGeometricRepresentationContext for the representation.
- **overall_height** (`Optional[float]`) : Overall door height. Defaults to 2m.
- **overall_width** (`Optional[float]`) : Overall door width. Defaults to 0.9m.
- **operation_type** (`Literal['SINGLE_SWING_LEFT', 'SINGLE_SWING_RIGHT', 'DOUBLE_SWING_RIGHT', 'DOUBLE_SWING_LEFT', 'DOUBLE_DOOR_SINGLE_SWING', 'DOUBLE_DOOR_DOUBLE_SWING', 'SLIDING_TO_LEFT', 'SLIDING_TO_RIGHT', 'DOUBLE_DOOR_SLIDING']`) , default: `SINGLE_SWING_LEFT` : Type of the door. Defaults to SINGLE_SWING_LEFT.
- **lining_properties** (`DoorLiningProperties | dict[str, Any] | None`) : DoorLiningProperties or a dictionary to create one. See DoorLiningProperties description for details.
- **panel_properties** (`DoorPanelProperties | dict[str, Any] | None`) : DoorPanelProperties or a dictionary to create one. See DoorPanelProperties description for details.
- **part_of_product** (`Optional[entity_instance]`)
- **unit_scale** (`Optional[float]`) : The unit scale as calculated by ifcopenshell.util.unit.calculate_unit_scale. If not provided, it will be automatically calculated for you.
## Returns

IfcShapeRepresentation for a door.
