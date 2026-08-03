# Patch: geometry.edit_object_placement

## Known Behavior: matrix uses world coordinates (ifcopenshell 0.8.x)

The `matrix` argument is interpreted as **world coordinates**. The usecase automatically writes compensating values against the container (Storey) placement chain, so the element's world position equals the matrix value.

**For multi-storey models, pass world z directly**: floor-2 slabs/railings/doors need `z=3.3` (is_si=True) — never pass "storey-local z=0". Passing 0 places the element at ground floor.

- Floor-2 slab `z=3.3`, flat roof `z=6.6`, balcony `z=3.3` (world coordinates)
- After placement, spot-check `world_xyz_mm` with `tracker.snapshot()`

Ref: `AI_IFC/examples/seaside_villa.py` (initial version misused local coords — all floor-2 elements ended up at ground level; caught by tracker coordinate check).
