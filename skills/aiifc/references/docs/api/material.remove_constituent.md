# material.remove_constituent

## API Definition

```python
def remove_constituent(model, constituent: entity_instance, should_remove_material: bool = False) -> None
```

*Source: api/material/remove_constituent*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_constituent", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_constituent(model, ...)`

## Description

Removes a constituent from a constituent set

Note that it is invalid to have zero items in a set, so you should leave at least one constituent to ensure a valid IFC dataset.

## Parameters

- **constituent** (`entity_instance`) : The IfcMaterialConstituent entity you want to remove
- **should_remove_material** (`bool`) , default: `False` : If true, materials with no users will be removed
## Returns

None
