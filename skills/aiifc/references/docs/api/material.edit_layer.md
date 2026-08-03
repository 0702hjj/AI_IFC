# material.edit_layer

## API Definition

```python
def edit_layer(model, layer: entity_instance, attributes: Optional[dict[str, Any]], material: Optional[entity_instance]) -> None
```

*Source: api/material/edit_layer*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_layer", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_layer(model, ...)`

## Description

Edits the attributes of an IfcMaterialLayer

For more information about the attributes and data types of an IfcMaterialLayer, consult the IFC documentation.

## Parameters

- **layer** (`entity_instance`) : The IfcMaterialLayer entity you want to edit
- **attributes** (`Optional[dict[str, Any]]`) : a dictionary of attribute names and values.
- **material** (`Optional[entity_instance]`) : The IfcMaterial entity you want the layer to be made from.
## Returns

None
