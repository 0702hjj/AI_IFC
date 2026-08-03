# profile.copy_profile

## API Definition

```python
def copy_profile(model, profile: entity_instance) -> entity_instance
```

*Source: api/profile/copy_profile*

## Import Surface

- run: `ifcopenshell.api.run("profile.copy_profile", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.copy_profile(model, ...)`

## Description

Copies a profile

All profile's psets are copied. The copied profile is not associated to any elements.

## Parameters

- **profile** (`entity_instance`) : The IfcProfileDef to copy
## Returns

The new copy of the profile
