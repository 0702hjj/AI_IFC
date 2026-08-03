# material.copy_material

## API Definition

```python
def copy_material(model, material: entity_instance) -> entity_instance
```

*Source: api/material/copy_material*

## Import Surface

- run: `ifcopenshell.api.run("material.copy_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.copy_material(model, ...)`

## Description

Copies a material or material set

All material psets and styles are copied. The copied material is not associated to any elements. If a material set is copied, the set items are also copied. However the underlying materials (and profiles) used within the set items are reused. If a material is associated with a presentation style, that presentation style is reused.

## Parameters

- **material** (`entity_instance`) : The IfcMaterialDefinition to copy
## Returns

The new copy of the material
