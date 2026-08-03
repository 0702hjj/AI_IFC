# material.remove_layer

## API Definition

```python
def remove_layer(model, layer: entity_instance, should_remove_material: bool = False) -> None
```

*Source: api/material/remove_layer*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_layer", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_layer(model, ...)`

## Description

Removes a layer from a layer set

Note that it is invalid to have zero items in a set, so you should leave at least one layer to ensure a valid IFC dataset.

## Parameters

- **layer** (`entity_instance`) : The IfcMaterialLayer entity you want to remove
- **should_remove_material** (`bool`) , default: `False` : If true, materials with no users will be removed
## Returns

None
