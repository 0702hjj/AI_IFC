# pset.unassign_pset

## API Definition

```python
def unassign_pset(model, products: list[entity_instance], pset: entity_instance) -> None
```

*Source: api/pset/unassign_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.unassign_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.unassign_pset(model, ...)`

## Description

Unassign property set from the provided elements.

## Parameters

- **products** (`list[entity_instance]`) : Elements (or element types) to assign the pset from.
- **pset** (`entity_instance`) : Property set.
## Returns

None
