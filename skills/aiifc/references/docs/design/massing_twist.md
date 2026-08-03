# Massing: Twisted Tower

## Parameters

| Parameter | Range | Default |
|---|---|---|
| Total twist | 45°–180° | 90° |
| Floor plate | Square/octagonal | 30×30 chamfer 5 |
| Core | Concrete, no rotation | 12×12 |

## Example Code

```python
TWIST_TOTAL = math.radians(90)
N_FLOORS = 20
for i, st in enumerate(storeys):
    theta = TWIST_TOTAL * i / N_FLOORS  # per-floor rotation
    verts = rot(BASE_VERTS, theta)      # rotate floor plate
    # Slab with rotated outline
    prof = add_arbitrary_profile(np.array(verts))
    # Curtain wall follows rotation
    for edge in rotated_edges:
        place(panel, x, y, z, phi=theta + edge_angle)
```