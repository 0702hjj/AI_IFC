# pset.assign_pset

## API Definition

```python
def assign_pset(model, products: list[entity_instance], pset: entity_instance) -> Optional[entity_instance]
```

*Source: api/pset/assign_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.assign_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.assign_pset(model, ...)`

## Description

Assign property set to provided elements.

This method can be used to make psets shared by multiple elements.

## Parameters

- **products** (`list[entity_instance]`) : Elements (or element types) to assign the pset to.
- **pset** (`entity_instance`) : Property set.
## Returns

None if `products` is empty or has only type elements. IfcRelDefinesByProperties if `products` contains occurrences.
