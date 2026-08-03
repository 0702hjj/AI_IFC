# spatial.dereference_structure

## API Definition

```python
def dereference_structure(model, products: list[entity_instance], relating_structure: entity_instance) -> None
```

*Source: api/spatial/dereference_structure*

## Import Surface

- run: `ifcopenshell.api.run("spatial.dereference_structure", model, ...)`
- direct: `import ifcopenshell.api.spatial; ifcopenshell.api.spatial.dereference_structure(model, ...)`

## Description

Dereferences a list of products and space

## Parameters

- **products** (`list[entity_instance]`) : The list of physical IfcElements that exists in the space.
- **relating_structure** (`entity_instance`) : The IfcSpatialStructureElement element, such as IfcBuilding, IfcBuildingStorey, or IfcSpace that the element exists in.
## Returns

None
