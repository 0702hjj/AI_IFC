# Patch: geometry.add_wall_representation

## Known Pattern: box primitive for non-wall elements (verified, shopping_mall)

`add_wall_representation` produces a cuboid box — usable as geometry for many non-wall element types:

| Element | Box params | Placement note |
|---|---|---|
| **Beam (IfcBeam)** | `length`=span, `height`=beam depth (Z), `thickness`=beam width | `edit_object_placement` rotates so box X-axis aligns with beam axis, Y-axis = width direction |
| **Escalator slope (IfcStairFlight)** | `length`=sloped length (_hypot(run, rise)), `height`=deck thickness (0.15m), `thickness`=width (1.5m), `x_angle`=atan2(rise, run) | Box tilts about X; base edge aligned to elevation |
| **Column (IfcColumn)** | `length`=side, `height`=storey height, `thickness`=other side (equal for square) | Box base aligned to storey base elevation |

Ref: `AI_IFC/examples/shopping_mall.py` (264 beams + 168 columns + 6 escalator slopes all based on this usecase).
