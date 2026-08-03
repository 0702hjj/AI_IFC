# material.add_material_set

## API Definition

```python
def add_material_set(model, name: str = Unnamed, set_type: Literal['IfcMaterialLayerSet', 'IfcMaterialProfileSet', 'IfcMaterialConstituentSet', 'IfcMaterialList'] = IfcMaterialConstituentSet) -> entity_instance
```

*Source: api/material/add_material_set*

## Import Surface

- run: `ifcopenshell.api.run("material.add_material_set", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_material_set(model, ...)`

## Description

Adds a new material set

IFC allows you to state that objects are made out of multiple materials. These are known generically as material sets, but may also be called layered materials, composite materials, or other names in software. There are three types of material sets: - A layer set, used for layered construction such as walls, where the element is parametrically made out of extruded layers, each layer having a thickness defined. Even though this is known as a layer "set" it is still recommended to use it for all standared layered construction as it describes the intent of the element to be layered construction and thus can be used for parametric editing. - A profile set, used for profiled construction such as beams or columns, where the element is parametrically made out of one or more extruded profiles, where each profile may be parametric from a standard section (e.g. standardised steel profile) or an arbitrary shape (e.g. cold rolled sections, or skirtings, moldings, etc). Note that even though this is called a profile "set", it should still be used even if there is only a single profile. This is not available in IFC2X3. - A constituent set, used for arbitrary composite construction where the object is made out of multiple materials. The constituents may be explicitly defined via a shape, such as a window where the frame geometry is made from one material and the panel geometry is made from another material. Alternatively, the constituents may be represented in terms of percentages, such as in mixtures like concrete where there might be a percentage constituent of cement and another percentage constituent of binder. This is not available in IFC2X3. There is also a fourth material set known as a material list, which is a legacy type of set used by IFC2X3. It should not be used on IFC4 and above, and constituent sets should be used instead.

## Parameters

- **name** (`str`) , default: `Unnamed` : The name of the material set, which may be purely descriptive or annotated in drawings. Defaults to "Unnamed".
- **set_type** (`Literal['IfcMaterialLayerSet', 'IfcMaterialProfileSet', 'IfcMaterialConstituentSet', 'IfcMaterialList']`) , default: `IfcMaterialConstituentSet` : What type of set you want to create, chosen from IfcMaterialLayerSet, IfcMaterialProfileSet, IfcMaterialConstituentSet, or IfcMaterialList. Defaults to IfcMaterialConstituentSet.
## Returns

The newly created material set element
