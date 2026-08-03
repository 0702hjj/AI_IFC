# profile.add_arbitrary_profile_with_voids

## API Definition

```python
def add_arbitrary_profile_with_voids(model, outer_profile: Sequence[Any] | ndarray, inner_profiles: list[Sequence[Any] | ndarray], name: Optional[str]) -> entity_instance
```

*Source: api/profile/add_arbitrary_profile_with_voids*

## Import Surface

- run: `ifcopenshell.api.run("profile.add_arbitrary_profile_with_voids", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.add_arbitrary_profile_with_voids(model, ...)`

## Description

Adds a new arbitrary polyline-based profile with voids

The outer profile is represented as a polyline defined by a list of coordinates. Only straight segments are allowed. Coordinates must be provided in SI meters. To represent a closed curve, the first and last coordinate must be identical. The inner profiles are represented as a list of polylines. Every polyline in defined by a list of coordinates. Only straight segments are allowed. Coordinates must be provided in SI meters.

## Parameters

- **outer_profile** (`Sequence[Any] | ndarray`) : A list of coordinates
- **inner_profiles** (`list[Sequence[Any] | ndarray]`) : A list of polylines
- **name** (`Optional[str]`) : If the profile is semantically significant (i.e. to be managed and reused by the user) then it must be named. Otherwise, this may be left as none.
## Returns

The newly created IfcArbitraryProfileDefWithVoids

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
