# material.edit_profile

## API Definition

```python
def edit_profile(model, profile: entity_instance, attributes: Optional[dict[str, Any]], profile_def: Optional[entity_instance], material: Optional[entity_instance]) -> None
```

*Source: api/material/edit_profile*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_profile", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_profile(model, ...)`

## Description

Edits the attributes of an IfcMaterialProfile

For more information about the attributes and data types of an IfcMaterialProfile, consult the IFC documentation.

## Parameters

- **profile** (`entity_instance`) : The IfcMaterialProfile entity you want to edit
- **attributes** (`Optional[dict[str, Any]]`) : a dictionary of attribute names and values.
- **profile_def** (`Optional[entity_instance]`) : The IfcProfileDef entity the profile curve should be extruded from.
- **material** (`Optional[entity_instance]`) : The IfcMaterial entity you want to change the profile to be made from.
## Returns

None
