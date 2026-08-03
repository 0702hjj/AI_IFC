# material.remove_list_item

## API Definition

```python
def remove_list_item(model, material_list: entity_instance, material_index: int = 0) -> None
```

*Source: api/material/remove_list_item*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_list_item", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_list_item(model, ...)`

## Description

Removes an item in an material list

Note that it is invalid to have zero items in a list, so you should leave at least one item to ensure a valid IFC dataset.

## Parameters

- **material_list** (`entity_instance`) : The IfcMaterialList entity you want to remove an item from.
- **material_index** (`int`) , default: `0` : The index of the material you want to remove from the list. Starts counting at 0. Defaults to 0.
## Returns

None
