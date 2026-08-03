# type.unassign_type

## API Definition

```python
def unassign_type(model, related_objects: list[entity_instance]) -> None
```

*Source: api/type/unassign_type*

## Import Surface

- run: `ifcopenshell.api.run("type.unassign_type", model, ...)`
- direct: `import ifcopenshell.api.type; ifcopenshell.api.type.unassign_type(model, ...)`

## Description

Unassigns a type from occurrences

Note that unassigning a type doesn't automatically remove mapped representations and material usages associated with the previously assigned type.

## Parameters

- **related_objects** (`list[entity_instance]`) : List of IfcElement occurrences.
## Returns

None
