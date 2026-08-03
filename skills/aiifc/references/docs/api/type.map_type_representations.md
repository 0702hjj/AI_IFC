# type.map_type_representations

## API Definition

```python
def map_type_representations(model, related_object: entity_instance, relating_type: entity_instance) -> None
```

*Source: api/type/map_type_representations*

## Import Surface

- run: `ifcopenshell.api.run("type.map_type_representations", model, ...)`
- direct: `import ifcopenshell.api.type; ifcopenshell.api.type.map_type_representations(model, ...)`

## Description

Ensures that all occurrences has the same representation as the type

If a type has a representation, all occurrences must have the same representation. If the type's representation changes, this function may be used to ensure consistency of the occurrence's representations.

## Parameters

- **related_object** (`entity_instance`) : The IfcElement occurrence.
- **relating_type** (`entity_instance`) : The IfcElementType type.
## Returns

None
