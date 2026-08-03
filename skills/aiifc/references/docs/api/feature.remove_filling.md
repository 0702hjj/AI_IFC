# feature.remove_filling

## API Definition

```python
def remove_filling(model, element: entity_instance) -> None
```

*Source: api/feature/remove_filling*

## Import Surface

- run: `ifcopenshell.api.run("feature.remove_filling", model, ...)`
- direct: `import ifcopenshell.api.feature; ifcopenshell.api.feature.remove_filling(model, ...)`

## Description

Remove a filling relationship

If an element is filling an opening, this removes the relationship such that the opening and element both still exist, but the element no longer fills the opening.

## Parameters

- **element** (`entity_instance`) : The element filling an opening.
## Returns

None
