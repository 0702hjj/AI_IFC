# geometry.edit_object_placement

## API Definition

```python
def edit_object_placement(model, product: entity_instance, matrix: Optional[NDArray[float64]], is_si: bool = True, should_transform_children: bool = False) -> entity_instance
```

*Source: api/geometry/edit_object_placement*

## Import Surface

- run: `ifcopenshell.api.run("geometry.edit_object_placement", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.edit_object_placement(model, ...)`

## Description

Changes the object placement matrix of an element

The placement matrix is a 4x4 matrix describing the location and orientation of an element in 3D. See https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html#object-placements for more details. This only supports local placements. Grid and linear placements are not supported.

## Parameters

- **product** (`entity_instance`)
- **matrix** (`Optional[NDArray[float64]]`) : A 4x4 matrix in numpy. If left blank, it is the identity matrix (equivalent to ``np.eye(4)``).
- **is_si** (`bool`) , default: `True` : If True, the matrix is given in SI units. If false, in project units.
- **should_transform_children** (`bool`) , default: `False` : A child element is a nested element, opening, filling, etc. If True, child elements move along with the parent; pass True when moving an assembly (roof, furniture group, etc.) and you want all children to follow. If False (default), child elements keep their current world positions; their local placements are rewritten to compensate for the parent move.
## Returns

The new or updated IfcLocalPlacement entity

## Known Behavior: matrix uses world coordinates (ifcopenshell 0.8.x)

The `matrix` argument is interpreted as **world coordinates**. The usecase automatically writes compensating values against the container (Storey) placement chain, so the element's world position equals the matrix value.

**For multi-storey models, pass world z directly**: floor-2 slabs/railings/doors need `z=3.3` (is_si=True) — never pass "storey-local z=0". Passing 0 places the element at ground floor.

- Floor-2 slab `z=3.3`, flat roof `z=6.6`, balcony `z=3.3` (world coordinates)
- After placement, spot-check `world_xyz_mm` with `tracker.snapshot()`
