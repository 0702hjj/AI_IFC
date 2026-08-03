# material.edit_profile_usage

## API Definition

```python
def edit_profile_usage(model, usage: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/material/edit_profile_usage*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_profile_usage", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_profile_usage(model, ...)`

## Description

Edits the attributes of an IfcMaterialProfileSetUsage

This is typically used to change the cardinal point of the profile. The cardinal point represents whether the profile is extruded along the center of the axis line, at a corner, at a shear center, at the bottom, top, etc. For more information about the attributes and data types of an IfcMaterialProfileSetUsage, consult the IFC documentation.

## Parameters

- **usage** (`entity_instance`) : The IfcMaterialProfileSetUsage entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
