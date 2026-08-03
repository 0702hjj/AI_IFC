# context.remove_context

## API Definition

```python
def remove_context(model, context: entity_instance) -> None
```

*Source: api/context/remove_context*

## Import Surface

- run: `ifcopenshell.api.run("context.remove_context", model, ...)`
- direct: `import ifcopenshell.api.context; ifcopenshell.api.context.remove_context(model, ...)`

## Description

Removes an IfcGeometricRepresentationContext

Any representation geometry that is assigned to the context is also removed. If a context is removed, then any subcontexts are also removed.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext entity to remove
## Returns

None
