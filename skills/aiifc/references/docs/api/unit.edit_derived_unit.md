# unit.edit_derived_unit

## API Definition

```python
def edit_derived_unit(model, unit: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/unit/edit_derived_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.edit_derived_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.edit_derived_unit(model, ...)`

## Description

Edits the attributes of an IfcDerivedUnit

For more information about the attributes and data types of an IfcDerivedUnit, consult the IFC documentation.

## Parameters

- **unit** (`entity_instance`) : The IfcDerivedUnit entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
