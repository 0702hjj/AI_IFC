# aggregate.unassign_object

## API Definition

```python
def unassign_object(model, products: list[entity_instance]) -> None
```

*Source: api/aggregate/unassign_object*

## Import Surface

- run: `ifcopenshell.api.run("aggregate.unassign_object", model, ...)`
- direct: `import ifcopenshell.api.aggregate; ifcopenshell.api.aggregate.unassign_object(model, ...)`

## Description

Unassigns products from their aggregate

A product (i.e. a smaller part of a whole) may be aggregated into zero or one larger space or element. This function will remove that aggregation relationship. As all physical IFC model elements must be part of a hierarchical tree called the "spatial decomposition", using this function will remove the product from that tree. This is a dangerous operation and may result in the product no longer being visible in IFC applications. If the product is not part of an aggregation relationship, nothing will happen.

## Parameters

- **products** (`list[entity_instance]`) : The list of parts of the aggregate, typically of IfcElements or IfcSpatialStructureElement subclass
## Returns

None
