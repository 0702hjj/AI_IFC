# unit.remove_unit

## API Definition

```python
def remove_unit(model, unit: entity_instance) -> None
```

*Source: api/unit/remove_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.remove_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.remove_unit(model, ...)`

## Description

Remove a unit

Be very careful when a unit is removed, as it may mean that previously defined quantities in the model completely lose their meaning.

## Parameters

- **unit** (`entity_instance`) : The unit element to remove
## Returns

None
