# geometry.validate_type

## API Definition

```python
def validate_type(model, representation: entity_instance, preferred_item: Optional[entity_instance]) -> bool
```

*Source: api/geometry/validate_type*

## Import Surface

- run: `ifcopenshell.api.run("geometry.validate_type", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.validate_type(model, ...)`

## Description

Validates the RepresentationType of an IfcShapeRepresentation

A shape representation has to identify its geometry using the RepresentationType attribute. For example, if it holds tessellated geometry, it should store "Tessellation" as its RepresentationType. This function checks whether or not the RepresentationType is valid. This is a wrapper around :func:`ifcopenshell.util.representation.guess_type`. It will then set RepresentationType to the most appropriate value, or return False otherwise. In addition, it also attempts to reconcile otherwise invalid CSG geometry by unioning all remaining top level items to existing boolean results.

## Parameters

- **representation** (`entity_instance`) : The IfcShapeRepresentation with Items
- **preferred_item** (`Optional[entity_instance]`) : If the type is expected to be a CSG, this will be the preferred item to union all remaining items to. If no preferred item is provided, the first boolean result will be chosen.
## Returns

True if the representation type was set and it is a valid combination, or False otherwise.
