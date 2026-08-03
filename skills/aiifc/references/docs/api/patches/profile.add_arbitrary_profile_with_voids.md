# Patch: profile.add_arbitrary_profile_with_voids

## Known Issue: vertices must include Z coordinate (ifcopenshell 0.8.5)

If `outer_profile` and `inner_profiles` use 2D coordinates `[(x,y), ...]`, the usecase produces `IfcCartesianPointList3D` entries without Z components, causing `ifcopenshell.validate` to reject with:

```
With attribute: <attribute CoordList: <list [3:3] of <type IfcLengthMeasure>>>
Value: (0.0, 0.0)  → Not valid
```

**Workaround: pad all coords with `z=0.0` as 3-tuples** (SI metres):

```python
pts = [[float(x), float(y), 0.0] for x, y in outer]
vds = [[[float(x), float(y), 0.0] for x, y in v] for v in inner_profiles]
ifcopenshell.api.run("profile.add_arbitrary_profile_with_voids", model,
    outer_profile=np.array(pts), inner_profiles=[np.array(v) for v in vds])
```

Ref: `AI_IFC/examples/shopping_mall.py` (atrium void slabs + skylight roof; initial version used 2D coords and failed validation; fixed by padding Z).
