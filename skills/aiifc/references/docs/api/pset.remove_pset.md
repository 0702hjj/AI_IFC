# pset.remove_pset

## API Definition

```python
def remove_pset(model, product: entity_instance, pset: entity_instance) -> None
```

*Source: api/pset/remove_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.remove_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.remove_pset(model, ...)`

## Description

Removes a property set from a product

All properties that are part of this property set are also removed.

## Parameters

- **product** (`entity_instance`) : The IfcObject to remove the property set from.
- **pset** (`entity_instance`) : The IfcPropertySet or IfcElementQuantity to remove.
## Returns

None
