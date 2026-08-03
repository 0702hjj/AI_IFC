# Patch: geometry.create_2pt_wall

## Known Behavior: elevation is world coordinates (ifcopenshell 0.8.x)

`p1` / `p2` / `elevation` all use **world coordinates**. If the wall is later assigned to a storey with elevation (e.g. floor 2 at z=3.3m), the usecase writes compensating values into the wall's `RelativePlacement` (e.g. -3300mm), preserving the world position specified by `elevation`.

**Multi-storey walls require world elevation**: floor-2 walls need `elevation=3.3m` — never pass `elevation=0` expecting "storey-local" coords. Passing 0 causes floor-2 walls to overlap ground-floor walls at z=0.

Verification: `tracker.snapshot()` → read `world_xyz_mm`; each storey's walls should report z = 0 / 3300 / ...
