# pset.unshare_pset

## API Definition

```python
def unshare_pset(model, products: list[entity_instance], pset: entity_instance) -> list[entity_instance]
```

*Source: api/pset/unshare_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.unshare_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.unshare_pset(model, ...)`

## Description

Copy a shared pset as linked only to the provided elements.

Note that method will create a copy of the pset for each element provided.

## Parameters

- **products** (`list[entity_instance]`) : Elements (or element types) to link the pset to.
- **pset** (`entity_instance`) : Shared property set.
## Returns

List of copied property sets.
