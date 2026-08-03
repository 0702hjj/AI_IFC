# geometry.add_shape_aspect

## API Definition

```python
def add_shape_aspect(model, name: str, items: list[entity_instance], representation: entity_instance, part_of_product: entity_instance, description: Optional[str]) -> entity_instance
```

*Source: api/geometry/add_shape_aspect*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_shape_aspect", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_shape_aspect(model, ...)`

## Description

Adds a shape aspect to items that are part of a representation and product

Existing shape aspects will be reused where possible. If the items already belong to another shape aspect with a different name, this relationship will be purged. Warning: it is not possible to add a shape aspect to types (i.e. IfcRepresentationMap) in IFC2X3.

## Parameters

- **name** (`str`) : The name of the shape aspect. This is case sensitive.
- **items** (`list[entity_instance]`) : IfcRepresentationItems that will be assigned to this aspect.
- **representation** (`entity_instance`) : The IfcShapeRepresentation that the items are in.
- **part_of_product** (`entity_instance`) : The IfcRepresentationMap or IfcProductDefinitionShape that the representation is in.
- **description** (`Optional[str]`) : A description to set for the shape aspect. It's usually not necessary.
## Returns

The IfcShapeAspect
