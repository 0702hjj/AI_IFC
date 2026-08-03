# unit.edit_named_unit

## API Definition

```python
def edit_named_unit(model, unit: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/unit/edit_named_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.edit_named_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.edit_named_unit(model, ...)`

## Description

Edits the attributes of an IfcNamedUnit

Named units include SI units, conversion based units (imperial units), and context dependent units. For more information about the attributes and data types of an IfcNamedUnit, consult the IFC documentation.

## Parameters

- **unit** (`entity_instance`) : The IfcNamedUnit entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
