# root.remove_product

## API Definition

```python
def remove_product(model, product: entity_instance) -> None
```

*Source: api/root/remove_product*

## Import Surface

- run: `ifcopenshell.api.run("root.remove_product", model, ...)`
- direct: `import ifcopenshell.api.root; ifcopenshell.api.root.remove_product(model, ...)`

## Description

Removes a product

This is effectively a smart delete function that not only removes a product, but also all of its relationships. It is always recommended to use this function to prevent orphaned data in your IFC model. This is intended to be used for removing: - IfcAnnotation - IfcElement - IfcElementType - IfcSpatialElement - IfcSpatialElementType For example, geometric representations are removed. Placement coordinates are also removed. Properties are removed. Material, type, containment, aggregation, and nesting relationships are removed (but naturally, the materials, types, containers, etc themselves remain).

## Parameters

- **product** (`entity_instance`) : The element to remove.
## Returns

None
