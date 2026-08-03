# unit.unassign_unit

## API Definition

```python
def unassign_unit(model, units: Optional[list[entity_instance]]) -> None
```

*Source: api/unit/unassign_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.unassign_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.unassign_unit(model, ...)`

## Description

Unassigns units as default units for the project

## Parameters

- **units** (`Optional[list[entity_instance]]`) : A list of units to unassign as project defaults.
## Returns

None
