# root.create_entity

## API Definition

```python
def create_entity(model, ifc_class: str = IfcBuildingElementProxy, predefined_type: Optional[str], name: Optional[str]) -> entity_instance
```

*Source: api/root/create_entity*

## Import Surface

- run: `ifcopenshell.api.run("root.create_entity", model, ...)`
- direct: `import ifcopenshell.api.root; ifcopenshell.api.root.create_entity(model, ...)`

## Description

Create a new rooted product

This is a critical function used to create almost any rooted product or product type. If you want to create walls, spaces, buildings, wall types, and so on, use this function. Just specify the class you want to create, as well as the predefined type and name. It will handle the storage of the predefined type and check whether the predefined type is built-in or custom. It will also generate a valid GlobalId and store ownership history. It will also handle some edge cases for default validity where users might forget to populate some mandatory attributes. For example, doors must define an operation type but many people forget.

## Parameters

- **ifc_class** (`str`) , default: `IfcBuildingElementProxy` : Any rooted IFC class.
- **predefined_type** (`Optional[str]`) : Any built-in or user-defined predefined type that is applicable to that IFC class. For user-defined predefined types just enter in any value and the API will handle it automatically.
- **name** (`Optional[str]`) : The name of the new element.
## Returns

The newly created element based on the specified IFC class.
