# unit.edit_monetary_unit

## API Definition

```python
def edit_monetary_unit(model, unit: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/unit/edit_monetary_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.edit_monetary_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.edit_monetary_unit(model, ...)`

## Description

Edits the attributes of an IfcMonetaryUnit

For more information about the attributes and data types of an IfcMonetaryUnit, consult the IFC documentation.

## Parameters

- **unit** (`entity_instance`) : The IfcMonetaryUnit entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
