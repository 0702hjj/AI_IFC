# geometry.add_boolean

## API Definition

```python
def add_boolean(model, first_item: entity_instance, second_items: list[entity_instance], operator: Literal['DIFFERENCE', 'INTERSECTION', 'UNION'] = DIFFERENCE) -> list[entity_instance]
```

*Source: api/geometry/add_boolean*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_boolean", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_boolean(model, ...)`

## Description

Adds a boolean operation to two or more representation items

This function protects against recursive booleans. After a boolean operation is made, since the items of IfcShapeRepresentation may be modified, it is not guaranteed that the RepresentationType is still valid. After performing all your booleans, it is recommended to run :func:`ifcopenshell.api.geometry.validate_csg` to ensure correctness.

## Parameters

- **first_item** (`entity_instance`) : The IfcBooleanOperand that the operation is performed upon
- **second_items** (`list[entity_instance]`) : The IfcBooleanOperands that the operation will be performed with, in the order given of the list.
- **operator** (`Literal['DIFFERENCE', 'INTERSECTION', 'UNION']`) , default: `DIFFERENCE` : The type of boolean operation to perform
## Returns

A list of newly created IfcBooleanResult in the order of boolean operations (based on the order of second items). If nothing was created, the list will be empty.
