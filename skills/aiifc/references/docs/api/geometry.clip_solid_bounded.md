# geometry.clip_solid_bounded

## API Definition

```python
def clip_solid_bounded(model, item: entity_instance, location: Sequence[float], normal: Sequence[float], boundary_points: Sequence[Sequence[float]], boundary_position: Sequence[float] = (0.0, 0.0, 0.0), element: Optional[entity_instance]) -> entity_instance
```

*Source: api/geometry/clip_solid_bounded*

## Import Surface

- run: `ifcopenshell.api.run("geometry.clip_solid_bounded", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.clip_solid_bounded(model, ...)`

## Description

Clip a solid with a polygonally bounded half-space, returning an IfcBooleanClippingResult.

Like :func:`clip_solid`, but the boolean subtraction is restricted to the region enclosed by ``boundary_points`` rather than extending across the entire half-space. The clipping plane is still infinite, but material is only removed within the extruded footprint of the polygon. The ``normal`` convention is the same as :func:`clip_solid`: it points toward the **removed** material. After clipping, set the parent ``IfcShapeRepresentation`` ``RepresentationType`` to ``"Clipping"``.

## Parameters

- **item** (`entity_instance`) : The solid to clip (``IfcSweptAreaSolid``, ``IfcSweptDiskSolid``, or ``IfcBooleanClippingResult``).
- **location** (`Sequence[float]`) : A point on the clipping plane in the representation's local coordinate system.
- **normal** (`Sequence[float]`) : Plane normal pointing toward the material to be removed.
- **boundary_points** (`Sequence[Sequence[float]]`) : 2D ``[x, y]`` points defining the closed polygonal boundary in the coordinate system of ``boundary_position``. The polygon is automatically closed — do not repeat the first point.
- **boundary_position** (`Sequence[float]`) , default: `(0.0, 0.0, 0.0)` : 3D origin of the boundary coordinate system (axes default to the global X/Y/Z directions). Defaults to the origin.
- **element** (`Optional[entity_instance]`) : If provided, the resulting ``IfcBooleanClippingResult`` is registered in the element's ``BBIM_Boolean`` property set so that :func:`regenerate_wall_representation` preserves it during regeneration.
## Returns

The resulting ``IfcBooleanClippingResult``.
