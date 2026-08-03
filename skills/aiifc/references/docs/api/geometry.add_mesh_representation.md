# geometry.add_mesh_representation

## API Definition

```python
def add_mesh_representation(model, context: entity_instance, vertices: list[Sequence[Any] | ndarray], edges: Optional[list[list[tuple[int, int]]]], faces: list[list[list[int]]], coordinate_offset: Optional[Any], unit_scale: Optional[float], force_faceted_brep: bool = False) -> entity_instance
```

*Source: api/geometry/add_mesh_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_mesh_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_mesh_representation(model, ...)`

## Description

Add a mesh representation.

Vertices, edges, and faces are given in the form of: ``[item1, item2, item3, ...]``. Each ``itemN`` is a sublist representing data for a separate IfcRepresentationItem to add. You can provide either ``edges`` or ``faces``, no need to provide both. But currently ``edges`` argument is not supported.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext for the representation.
- **vertices** (`list[Sequence[Any] | ndarray]`) : A list of coordinates. where ``itemN = [(0., 0., 0.), (1., 1., 1.), (x, y, z), ...]``
- **edges** (`Optional[list[list[tuple[int, int]]]]`) : A list of edges, represented by vertex index pairs where ``itemN = [(0, 1), (1, 2), (v1, v2), ...]``
- **faces** (`list[list[list[int]]]`) : A list of polygons, represented by vertex indices. where ``itemN = [(0, 1, 2), (5, 4, 2, 3), (v1, v2, v3, ... vN), ...]``
- **coordinate_offset** (`Optional[Any]`) : Optionally apply a vector offset to all coordinates. In project units.
- **unit_scale** (`Optional[float]`) : Scale factor for ``vertices`` units.
- **force_faceted_brep** (`bool`) , default: `False` : Force using IfcFacetedBreps instead of IfcPolygonalFaceSets.
## Returns

IfcShapeRepresentation.
