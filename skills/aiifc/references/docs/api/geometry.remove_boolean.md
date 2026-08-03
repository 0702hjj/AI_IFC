# geometry.remove_boolean

## API Definition

```python
def remove_boolean(model, item: entity_instance) -> None
```

*Source: api/geometry/remove_boolean*

## Import Surface

- run: `ifcopenshell.api.run("geometry.remove_boolean", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.remove_boolean(model, ...)`

## Description

Removes a boolean operation without deleting the operands

The first operand will replace the boolean result itself, and the second operand will be reset as a top level representation item. This may affect the Items of IfcShapeRepresentation, so it is recommended to run :func:`ifcopenshell.api.geometry.validate_type` after all boolean modifications are complete.

## Parameters

- **item** (`entity_instance`) : This may either be an IfcBooleanResult or an IfcRepresentationItem that is participating in one or more boolean results (in which case all are removed).
## Returns

None
