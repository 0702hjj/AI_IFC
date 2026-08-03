# geometry.connect_path

## API Definition

```python
def connect_path(model, relating_element: entity_instance, related_element: entity_instance, relating_connection: str = NOTDEFINED, related_connection: str = NOTDEFINED, description: Optional[str], connection_geometry: Optional[entity_instance]) -> entity_instance
```

*Source: api/geometry/connect_path*

## Import Surface

- run: `ifcopenshell.api.run("geometry.connect_path", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.connect_path(model, ...)`

## Description



## Parameters

- **relating_element** (`entity_instance`)
- **related_element** (`entity_instance`)
- **relating_connection** (`str`) , default: `NOTDEFINED`
- **related_connection** (`str`) , default: `NOTDEFINED`
- **description** (`Optional[str]`)
- **connection_geometry** (`Optional[entity_instance]`)
## Returns

entity_instance
