# material.edit_material

## API Definition

```python
def edit_material(model, material: entity_instance, attributes: dict[str, Any]) -> None
```

*Source: api/material/edit_material*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_material(model, ...)`

## Description

Edits the attributes of an IfcMaterial

## Parameters

- **material** (`entity_instance`)
- **attributes** (`dict[str, Any]`)
## Returns

None
