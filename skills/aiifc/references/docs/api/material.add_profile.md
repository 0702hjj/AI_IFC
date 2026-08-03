# material.add_profile

## API Definition

```python
def add_profile(model, profile_set: entity_instance, material: Optional[entity_instance], profile: Optional[entity_instance], name: Optional[str]) -> entity_instance
```

*Source: api/material/add_profile*

## Import Surface

- run: `ifcopenshell.api.run("material.add_profile", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_profile(model, ...)`

## Description

Add a new profile item to a profile set

A profile item in a profile set represents an extruded 2D profile curve that is extruded along the axis of the element. Most commonly there will only be a single profile item in a profile set. For example, a beam will have a material profile set containing a single profile item, which may have a steel material and a I-beam shaped profile curve. Note that the "profile item" represents a single extrusion in the profile set, whereas the "profile curve" represents a 2D curve used by a "profile item". Profile is not optional for IfcMaterialProfile but it is optional for this API call and can be assigned later with material.assign_profile. In some cases, a profiled element (i.e. beam, column) may be a composite beam or column and include multiple extrusions. This is rare. The order of the profiles does not matter.

## Parameters

- **profile_set** (`entity_instance`) : The IfcMaterialProfileSet that the profile is part of. The profile set represents a group of profile items. See ifcopenshell.api.material.add_material_set for more information on how to add a profile set.
- **material** (`Optional[entity_instance]`) : The IfcMaterial that the profile item is made out of.
- **profile** (`Optional[entity_instance]`) : The IfcProfileDef that represents the 2D cross section of the the profile item.
- **name** (`Optional[str]`) : An optional name of the material profile (not the geometric profile).
## Returns

The newly created IfcMaterialProfile
