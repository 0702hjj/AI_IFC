# material.reorder_set_item

## API Definition

```python
def reorder_set_item(model, material_set: entity_instance, old_index: int = 0, new_index: int = 0) -> None
```

*Source: api/material/reorder_set_item*

## Import Surface

- run: `ifcopenshell.api.run("material.reorder_set_item", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.reorder_set_item(model, ...)`

## Description

Reorders an item in a material set

In some material sets, the order have meaning, like in a layer set. In other cases, it is purely for human convenience.

## Parameters

- **material_set** (`entity_instance`) : The IfcMaterialSet which you want to reorder an item in.
- **old_index** (`int`) , default: `0` : The index of the item you want to move. This starts counting from 0.
- **new_index** (`int`) , default: `0` : The index of the new position the item will move to. This starts counting from 0.
## Returns

None
