# profile.edit_profile

## API Definition

```python
def edit_profile(model, profile: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/profile/edit_profile*

## Import Surface

- run: `ifcopenshell.api.run("profile.edit_profile", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.edit_profile(model, ...)`

## Description

Edits the attributes of an IfcProfileDef

For more information about the attributes and data types of an IfcProfileDef, consult the IFC documentation.

## Parameters

- **profile** (`entity_instance`) : The IfcProfileDef entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
