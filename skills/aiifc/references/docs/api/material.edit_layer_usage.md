# material.edit_layer_usage

## API Definition

```python
def edit_layer_usage(model, usage: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/material/edit_layer_usage*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_layer_usage", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_layer_usage(model, ...)`

## Description

Edits the attributes of an IfcMaterialLayerSetUsage

This is typically used to change the offset from the reference line to the layers. For more information about the attributes and data types of an IfcMaterialLayerSetUsage, consult the IFC documentation.

## Parameters

- **usage** (`entity_instance`) : The IfcMaterialLayerSetUsage entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
