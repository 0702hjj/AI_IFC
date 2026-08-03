# profile.add_arbitrary_profile

## API Definition

```python
def add_arbitrary_profile(model, profile: Sequence[Any] | ndarray, name: Optional[str]) -> entity_instance
```

*Source: api/profile/add_arbitrary_profile*

## Import Surface

- run: `ifcopenshell.api.run("profile.add_arbitrary_profile", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.add_arbitrary_profile(model, ...)`

## Description

Adds a new arbitrary polyline-based profile

The profile is represented as a polyline defined by a list of coordinates. Only straight segments are allowed. Coordinates must be provided in SI meters. To represent a closed curve, the first and last coordinate must be identical.

## Parameters

- **profile** (`Sequence[Any] | ndarray`) : A list of coordinates
- **name** (`Optional[str]`) : If the profile is semantically significant (i.e. to be managed and reused by the user) then it must be named. Otherwise, this may be left as none.
## Returns

The newly created IfcArbitraryClosedProfileDef
