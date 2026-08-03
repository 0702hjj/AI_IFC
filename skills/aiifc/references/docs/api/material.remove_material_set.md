# material.remove_material_set

## API Definition

```python
def remove_material_set(model, material: entity_instance) -> None
```

*Source: api/material/remove_material_set*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_material_set", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_material_set(model, ...)`

## Description

Removes a material set

All set items, such as layers, profiles, or constituents will also be removed. All set usages are also removed. However, the materials and profile curves used by the layers, profiles and constituents will not be removed.

## Parameters

- **material** (`entity_instance`) : The IfcMaterialLayerSet, IfcMaterialConstituentSet, IfcMaterialProfileSet entity you want to remove.
## Returns

None
