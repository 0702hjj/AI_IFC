# context.edit_context

## API Definition

```python
def edit_context(model, context: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/context/edit_context*

## Import Surface

- run: `ifcopenshell.api.run("context.edit_context", model, ...)`
- direct: `import ifcopenshell.api.context; ifcopenshell.api.context.edit_context(model, ...)`

## Description

Edits the attributes of an IfcGeometricRepresentationContext

For more information about the attributes and data types of an IfcGeometricRepresentationContext, consult the IFC documentation.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext entity you want to edit
- **attributes** (`dict[str, Any]`) : a dictionary of attribute names and values.
## Returns

None
