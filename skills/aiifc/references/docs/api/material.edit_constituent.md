# material.edit_constituent

## API Definition

```python
def edit_constituent(model, constituent: entity_instance, attributes: Optional[dict[str, Any]], material: Optional[entity_instance]) -> None
```

*Source: api/material/edit_constituent*

## Import Surface

- run: `ifcopenshell.api.run("material.edit_constituent", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.edit_constituent(model, ...)`

## Description

Edits the attributes of an IfcMaterialConstituent

For more information about the attributes and data types of an IfcMaterialConstituent, consult the IFC documentation.

## Parameters

- **constituent** (`entity_instance`) : The IfcMaterialConstituent entity you want to edit
- **attributes** (`Optional[dict[str, Any]]`) : a dictionary of attribute names and values.
- **material** (`Optional[entity_instance]`) : The IfcMaterial entity you want to change the constituent to
## Returns

None
