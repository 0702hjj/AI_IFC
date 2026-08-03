# material.remove_profile

## API Definition

```python
def remove_profile(model, profile: entity_instance, should_remove_profile_def: bool = False, should_remove_material: bool = False) -> None
```

*Source: api/material/remove_profile*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_profile", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_profile(model, ...)`

## Description

Removes a profile item from a profile set

Note that it is invalid to have zero items in a set, so you should leave at least one profile to ensure a valid IFC dataset.

## Parameters

- **profile** (`entity_instance`) : The IfcMaterialProfile entity you want to remove
- **should_remove_profile_def** (`bool`) , default: `False` : If true, profile defs with no users will be removed
- **should_remove_material** (`bool`) , default: `False` : If true, materials with no users will be removed
## Returns

None
