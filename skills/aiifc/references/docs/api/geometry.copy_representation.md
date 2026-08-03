# geometry.copy_representation

## API Definition

```python
def copy_representation(model, source: entity_instance, target: entity_instance, context_identifier: str = Body) -> Optional[entity_instance]
```

*Source: api/geometry/copy_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.copy_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.copy_representation(model, ...)`

## Description

Copy a geometric representation from one element to another.

Finds the named representation on ``source``, deep-copies its entity graph (geometry items, profiles, placements, etc.), and assigns the copy to ``target``. Representation contexts are shared rather than copied. If ``target`` already has a matching representation it is removed and replaced. If no matching representation is found on ``source``, returns ``None`` and leaves ``target`` unchanged.

## Parameters

- **source** (`entity_instance`) : The element to copy the representation from.
- **target** (`entity_instance`) : The element to assign the copied representation to.
- **context_identifier** (`str`) , default: `Body` : The RepresentationIdentifier to look up on ``source`` (e.g. ``"Body"``, ``"Axis"``, ``"Box"``). Defaults to ``"Body"``.
## Returns

The newly created IfcShapeRepresentation, or None if no matching representation was found on ``source``.
