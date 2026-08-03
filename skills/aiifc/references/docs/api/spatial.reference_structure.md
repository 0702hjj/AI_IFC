# spatial.reference_structure

## API Definition

```python
def reference_structure(model, products: list[entity_instance], relating_structure: entity_instance) -> Optional[entity_instance]
```

*Source: api/spatial/reference_structure*

## Import Surface

- run: `ifcopenshell.api.run("spatial.reference_structure", model, ...)`
- direct: `import ifcopenshell.api.spatial; ifcopenshell.api.spatial.reference_structure(model, ...)`

## Description

Denote that a list products is related to a list of spatial structures

This is similar to ifcopenshell.api.spatial.assign_container, except that containment can only occur between a product and a single spatial structure element. This is fine if a wall is on level 1, but not appropriate if you have a multistorey column on multiple levels, or a door with a to and from space, or a stair going from one floor to another floor. This is where spatial referencing is used. Typically, the product will be contained in the lowermost, constructed first, or primarily accessible space. For a multistorey column or stair, the column or stair will therefore be contained in the lowermost storey. Then, any other storeys will be referenced. Referencing is non-hierarchical, so a door may be referenced in multiple spaces simultaneously.

## Parameters

- **products** (`list[entity_instance]`) : The list of physical IfcElements that exists in the space.
- **relating_structure** (`entity_instance`) : The IfcSpatialStructureElement element, such as IfcBuilding, IfcBuildingStorey, or IfcSpace that the element exists in.
## Returns

The IfcRelReferencedInSpatialStructure relationship instance or `None` if `products` was an empty list.
