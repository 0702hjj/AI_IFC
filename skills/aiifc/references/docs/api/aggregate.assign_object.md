# aggregate.assign_object

## API Definition

```python
def assign_object(model, products: list[entity_instance], relating_object: entity_instance) -> Optional[entity_instance]
```

*Source: api/aggregate/assign_object*

## Import Surface

- run: `ifcopenshell.api.run("aggregate.assign_object", model, ...)`
- direct: `import ifcopenshell.api.aggregate; ifcopenshell.api.aggregate.assign_object(model, ...)`

## Description

Assigns object as an aggregate to the products

All physical IFC model elements must be part of a hierarchical tree called the "spatial decomposition", where large things are made up of smaller things. This tree always begins at an "IfcProject" and is then broken down using "decomposition" relationships, of which aggregation is the first relationship you will use. Typically used when you want to describe how large spaces are made up of smaller spaces. For example large spatial elements (e.g. sites, buidings) can be made out of smaller spatial elements (e.g. storeys, spaces). The largest space (typically the IfcSite) can then be aggregated in a project. It is requirement for all spatial structures to be directly or indirectly aggregated back to the IfcProject to create a hierarchy of spaces. The other common usecase is when larger physical products are made up of smaller physical products. For example, a stair might be made out of a flight, a landing, a railing and so on. Or a wall might be made out of stud members, and coverings. As a product may only have a single location in the "spatial decomposition" tree, assigning an aggregate relationship will remove any previous aggregation, containment, or nesting relationships it may have. IFC placements follow a convention where the placement is relative to its parent in the spatial hierarchy. If your product has a placement, its placement will be recalculated to follow this convention.

## Parameters

- **products** (`list[entity_instance]`) : The list of parts of the aggregate, typically of IfcElement or IfcSpatialStructureElement subclass
- **relating_object** (`entity_instance`) : The whole of the aggregate, typically an IfcElement or IfcSpatialStructureElement subclass
## Returns

The IfcRelAggregate relationship instance or `None` if `products` was empty list.
