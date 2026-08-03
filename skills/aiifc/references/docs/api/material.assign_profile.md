# material.assign_profile

## API Definition

```python
def assign_profile(model, material_profile: entity_instance, profile: entity_instance) -> None
```

*Source: api/material/assign_profile*

## Import Surface

- run: `ifcopenshell.api.run("material.assign_profile", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.assign_profile(model, ...)`

## Description

Changes the profile curve of a material profile item in a profile set

In addition to changing the profile curve, it will also change the profile curve used in any body representation extrusions.

## Parameters

- **material_profile** (`entity_instance`) : The IfcMaterialProfile to change the profile curve of. See ifcopenshell.api.material.add_profile to see how to create profiles.
- **profile** (`entity_instance`) : The IfcProfileDef to set the profile item's curve to.
## Returns

None
