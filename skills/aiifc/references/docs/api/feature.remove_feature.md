# feature.remove_feature

## API Definition

```python
def remove_feature(model, feature: entity_instance) -> None
```

*Source: api/feature/remove_feature*

## Import Surface

- run: `ifcopenshell.api.run("feature.remove_feature", model, ...)`
- direct: `import ifcopenshell.api.feature; ifcopenshell.api.feature.remove_feature(model, ...)`

## Description

Permanently delete a feature element and its void or projection relationship.

The feature entity (e.g. IfcOpeningElement) is removed from the model along with its IfcRelVoidsElement or IfcRelProjectsElement relationship. The host element (wall, slab, etc.) is unaffected. Any fillings (windows, doors) that occupied the opening become orphaned and must be separately deleted via root.remove_product.

## Parameters

- **feature** (`entity_instance`) : The IfcFeatureElement to remove.
## Returns

None
