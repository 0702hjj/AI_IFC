# spatial.assign_container

## API Definition

```python
def assign_container(model, products: list[entity_instance], relating_structure: entity_instance) -> Optional[entity_instance]
```

*Source: api/spatial/assign_container*

## Import Surface

- run: `ifcopenshell.api.run("spatial.assign_container", model, ...)`
- direct: `import ifcopenshell.api.spatial; ifcopenshell.api.spatial.assign_container(model, ...)`

## Description

Assigns products to be contained hierarchically in a space

All physical IFC model elements must be part of a hierarchical tree called the "spatial decomposition", where large things are made up of smaller things. This tree always begins at an "IfcProject" and is then broken down using "decomposition" relationships, of which aggregation is the first relationship you will use. See ifcopenshell.api.aggregate.assign_object for more details about aggregation. The IfcProject will be "decomposed" into spatial structure elements. These are virtual spaces like stes, buildings, storeys, and spaces (i.e. rooms). You can't physically touch these spaces, but you can touch the products contained within these spaces. To state that a product is contained in a space, you will use a "containment" relationship. Containment is a very common relationship used to create the hierarchical spatial decomposition tree. For example, you might say that "This wall is on the third building storey", or "this table is in the living room space". The distinguishing factor between aggregation and containment is that aggregation occurs between objects of the same type (e.g. a large space is made up of smaller spaces), whereas containment is between two different types: explicitly saying that a physical product exists within a virtual space. Containment is critical in construction management, to know which objects are in which spaces, as often you would divide your construction schedule into storey by storey, or zone by zone. Containment is also critical in facility management, as it indicates through which space equipment may be accessed for maintenance purposes. As a product may only have a single location in the "spatial decomposition" tree, assigning an aggregate relationship will remove any previous aggregation, containment, or nesting relationships it may have.

## Parameters

- **products** (`list[entity_instance]`) : A list of physical IfcElements existing in the space.
- **relating_structure** (`entity_instance`) : The IfcSpatialStructureElement element, such as IfcBuilding, IfcBuildingStorey, or IfcSpace that the element exists in.
## Returns

The IfcRelContainedInSpatialStructure relationship instance or `None` if `products` was empty list.
