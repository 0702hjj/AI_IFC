# material.unassign_material

## API Definition

```python
def unassign_material(model, products: list[entity_instance]) -> None
```

*Source: api/material/unassign_material*

## Import Surface

- run: `ifcopenshell.api.run("material.unassign_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.unassign_material(model, ...)`

## Description

Removes any material relationship with the list of products

A product can only have one material assigned to it, which is why it is not necessary to specify the material to unassign. The material is not removed, only the relationship is removed. If the product does not have a material, nothing happens. Unassigning a LayerSet or ProfileSet from the product type will also remove all Usages of the set.

## Parameters

- **products** (`list[entity_instance]`) : The list IfcProducts that may or may not have a material
## Returns

None
