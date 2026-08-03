# material.remove_material

## API Definition

```python
def remove_material(model, material: entity_instance) -> None
```

*Source: api/material/remove_material*

## Import Surface

- run: `ifcopenshell.api.run("material.remove_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.remove_material(model, ...)`

## Description

Removes a material

If the material is used in a material set, the corresponding layer, profile, or constituent is also removed. Note that this may result in a material set with zero items in it, which is invalid, so the user must take care of this situation themselves.

## Parameters

- **material** (`entity_instance`) : The IfcMaterial entity you want to remove
## Returns

None
