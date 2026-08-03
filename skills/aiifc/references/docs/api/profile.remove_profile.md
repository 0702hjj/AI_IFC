# profile.remove_profile

## API Definition

```python
def remove_profile(model, profile: entity_instance) -> None
```

*Source: api/profile/remove_profile*

## Import Surface

- run: `ifcopenshell.api.run("profile.remove_profile", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.remove_profile(model, ...)`

## Description

Removes a profile

## Parameters

- **profile** (`entity_instance`) : The IfcProfileDef to remove.
## Returns

None
