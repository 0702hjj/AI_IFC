# material.add_constituent

## API Definition

```python
def add_constituent(model, constituent_set: entity_instance, material: entity_instance, name: Optional[str]) -> entity_instance
```

*Source: api/material/add_constituent*

## Import Surface

- run: `ifcopenshell.api.run("material.add_constituent", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_constituent(model, ...)`

## Description

Adds a new constituent to a constituent set

A constituent describes how a portion of an object is made out of a material whereas other portions of the object is made out of other materials. For example, a window might be made out of an aluminium frame and a glass panel. The aluminium used for the frame is one constituent of the material, and glass would be another constituent. Another example might be concrete, where one constituent might be cement, and another constituent might be binder. In the case of the window, the constituent is represented explicitly by the geometry of the window frame and the geometry of the window panel. In the case of a concrete slab, the constituents might be represented in terms of percentages. Constituents are not available in IFC2X3.

## Parameters

- **constituent_set** (`entity_instance`) : The IfcMaterialConstituentSet that the constituent is part of. The constituent set represents a group of constituents. See ifcopenshell.api.material.add_material_set for information on how to add a constituent set.
- **material** (`entity_instance`) : The IfcMaterial that the constituent is made out of.
- **name** (`Optional[str]`) : An optional name of the constituent.
## Returns

The newly created IfcMaterialConstituent
