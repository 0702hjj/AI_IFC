# feature.add_filling

## API Definition

```python
def add_filling(model, opening: entity_instance, element: entity_instance) -> entity_instance
```

*Source: api/feature/add_filling*

## Import Surface

- run: `ifcopenshell.api.run("feature.add_filling", model, ...)`
- direct: `import ifcopenshell.api.feature; ifcopenshell.api.feature.add_filling(model, ...)`

## Description

Fill an opening with an element

Physical elements may have openings in them. For example, a wall might have an opening for a door. That opening is then filled by the door. This indicates that when the door moves, the opening will move with it. Or if the door is removed, then the opening may remain and need to be filled.

## Parameters

- **opening** (`entity_instance`) : The IfcOpeningElement to fill with the element.
- **element** (`entity_instance`) : The IfcElement to be inserted into the opening.
## Returns

The new IfcRelFillsElement relationship
