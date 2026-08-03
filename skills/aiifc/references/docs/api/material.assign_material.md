# material.assign_material

## API Definition

```python
def assign_material(model, products: list[entity_instance], type: Literal['IfcMaterial', 'IfcMaterialConstituentSet', 'IfcMaterialLayerSet', 'IfcMaterialLayerSetUsage', 'IfcMaterialProfileSet', 'IfcMaterialProfileSetUsage', 'IfcMaterialList'] = IfcMaterial, material: Optional[entity_instance]) -> entity_instance | list[entity_instance] | None
```

*Source: api/material/assign_material*

## Import Surface

- run: `ifcopenshell.api.run("material.assign_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.assign_material(model, ...)`

## Description

Assigns a material to the list of products

Will unassign previously assigned material. When a material is assigned to a product, it means that the product is made out of that material. In its simplest form, a single material may be assigned to a product, meaning that the entire product is made out of that one material. Alternatively, a material set may be assigned to a product, meaning that the product is made out of a set of materials. There are three types of sets, including layered construction, profiled materials, and arbitrary material constituents. See ifcopenshell.api.material.add_material_set for details. Materials are typically assigned to the element types rather than individual occurrences of elements. Individual occurrences would then inherit the material from the type. If the type has a material set, then the geometry of the occurrences must comply with the material set. For example, if the type has a constituent set, then it is expected that all occurrences also inherit the geometry of the type, which is made out of those constituents. Alternatively, if the type has a layer set, then all occurrences must have geometry that has a thickness equal to the sum of all layers. If a type has a profile set, then all occurrences must has the same profile extruded along its axis. For layers and profiles assigned to types, the occurrences must be assigned an IfcMaterialLayerSetUsage or an IfcMaterialProfileSetUsage. This allows individual occurrences to override the layered or profiled construction offset from a reference line.

## Parameters

- **products** (`list[entity_instance]`) : The list of IfcProducts to assign the material or material set to.
- **type** (`Literal['IfcMaterial', 'IfcMaterialConstituentSet', 'IfcMaterialLayerSet', 'IfcMaterialLayerSetUsage', 'IfcMaterialProfileSet', 'IfcMaterialProfileSetUsage', 'IfcMaterialList']`) , default: `IfcMaterial` : Choose from "IfcMaterial", "IfcMaterialConstituentSet", "IfcMaterialLayerSet", "IfcMaterialLayerSetUsage", "IfcMaterialProfileSet", "IfcMaterialProfileSetUsage", or "IfcMaterialList". Note that "Set Usages" may only be assigned to occurrences, not types. Defaults to "IfcMaterial".
- **material** (`Optional[entity_instance]`) : The IfcMaterial or material set you are assigning here. If type is Usage then no need to provide `material`, it will be deduced from the element type automatically. If IfcMaterial is provided as material and type is not IfcMaterial, provided material will be ignored except for IfcMaterialList where it will be used as part of the list.
## Returns

IfcRelAssociatesMaterial entity or a list of IfcRelAssociatesMaterial entities (possible if `type` is Usage and `products` require different Usages) or `None` if `products` was empty list.
