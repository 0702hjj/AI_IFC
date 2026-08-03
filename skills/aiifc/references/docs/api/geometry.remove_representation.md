# geometry.remove_representation

## API Definition

```python
def remove_representation(model, representation: entity_instance, should_keep_named_profiles: bool = True) -> None
```

*Source: api/geometry/remove_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.remove_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.remove_representation(model, ...)`

## Description

Remove a representation.

Also purges representation items and their related elements like IfcStyledItem, tessellated facesets colours and UV map. By default, named profiles are assumed to be significant (i.e. curated as part of a profile library) and will not be removed.

## Parameters

- **representation** (`entity_instance`) : IfcRepresentation to remove. Note that it's expected that IfcRepresentation won't be in use before calling this method (in such elements as IfcProductRepresentation, IfcShapeAspect) otherwise representation won't be removed.
- **should_keep_named_profiles** (`bool`) , default: `True` : If true, named profile defs will not be removed as they are assumed to be significant.
## Returns

None
