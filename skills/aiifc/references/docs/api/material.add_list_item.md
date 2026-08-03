# material.add_list_item

## API Definition

```python
def add_list_item(model, material_list: entity_instance, material: entity_instance) -> None
```

*Source: api/material/add_list_item*

## Import Surface

- run: `ifcopenshell.api.run("material.add_list_item", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_list_item(model, ...)`

## Description

Adds a new material in a list of materials

In IFC2X3, if you wanted an object to have multiple materials (i.e. a composite material) you would assign the object to a material list, which would contain a list of materials. For example, a window might have a list of 2 materials, one being aluminium for the frame, and another being glass for the panel. In IFC4 and above, this is deprecated and should not be used. Instead, you should use constituent sets instead, which achieve the same thing but are more powerful as they allow you to define the properties of the constituents too. However if you're stuck on IFC2X3, you have my condolences as well as this function.

## Parameters

- **material_list** (`entity_instance`) : The IfcMaterialList the material should be added to.
- **material** (`entity_instance`) : The IfcMaterial to add to the list
## Returns

None
