# geometry.disconnect_path

## API Definition

```python
def disconnect_path(model, element: Optional[entity_instance], connection_type: Optional[str], relating_element: Optional[entity_instance], related_element: Optional[entity_instance]) -> None
```

*Source: api/geometry/disconnect_path*

## Import Surface

- run: `ifcopenshell.api.run("geometry.disconnect_path", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.disconnect_path(model, ...)`

## Description

There are two options to use this API method:

## Parameters

- **element** (`Optional[entity_instance]`)
- **connection_type** (`Optional[str]`)
- **relating_element** (`Optional[entity_instance]`)
- **related_element** (`Optional[entity_instance]`)
## Returns

None
