# material.edit_assigned_material

## API Definition

```python
def edit_assigned_material(model, element: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/material/edit_assigned_material*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_assigned_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_assigned_material(model, ...)`

## Description

Edits the attributes of an IfcMaterial

For more information about the attributes and data types of an IfcMaterial, consult the IFC documentation.

## Parameters

- **element** (`entity_instance`) : The IfcMaterial entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
