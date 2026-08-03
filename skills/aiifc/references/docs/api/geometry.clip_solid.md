# geometry.clip_solid

## API Definition

```python
def clip_solid(model, item: entity_instance, location: Sequence[float], normal: Sequence[float], element: Optional[entity_instance]) -> entity_instance
```

*Source: api/geometry/clip_solid*

## Import Surface

- run: `ifcopenshell.api.run("geometry.clip_solid", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.clip_solid(model, ...)`

## Description

Clip a solid with a half-space plane, returning an IfcBooleanClippingResult.

Convenience wrapper around :class:`ifcopenshell.util.data.Clipping` for use with any solid. This is the same convention used by the ``clippings`` parameter of :func:`add_wall_representation`. .. warning:: The ``normal`` points toward the **removed** material (the discarded side), not toward the kept material. For a slope clip the normal points upward into the removed wedge above the slope line. For a side mitre the normal points outward away from the wall body. After clipping, set the parent ``IfcShapeRepresentation`` ``RepresentationType`` to ``"Clipping"``.

## Parameters

- **item** (`entity_instance`) : The solid to clip (``IfcSweptAreaSolid``, ``IfcSweptDiskSolid``, or ``IfcBooleanClippingResult``).
- **location** (`Sequence[float]`) : A point on the clipping plane in the representation's local coordinate system.
- **normal** (`Sequence[float]`) : Plane normal pointing toward the material to be removed (see warning above).
- **element** (`Optional[entity_instance]`) : If provided, the resulting ``IfcBooleanClippingResult`` is registered in the element's ``BBIM_Boolean`` property set so that :func:`regenerate_wall_representation` preserves it during regeneration.
## Returns

The resulting ``IfcBooleanClippingResult``.
