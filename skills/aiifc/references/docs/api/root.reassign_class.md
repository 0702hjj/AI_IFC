# root.reassign_class

## API Definition

```python
def reassign_class(model, product: entity_instance, ifc_class: str = IfcBuildingElementProxy, predefined_type: Optional[str], occurrence_class: Optional[str]) -> entity_instance
```

*Source: api/root/reassign_class*

## Import Surface

- run: `ifcopenshell.api.run("root.reassign_class", model, ...)`
- direct: `import ifcopenshell.api.root; ifcopenshell.api.root.reassign_class(model, ...)`

## Description

Changes the class of a product

If you ever created a wall then realised it's meant to be something else, this function lets you change the IFC class whilst retaining all other geometry and relationships. This is especially useful when dealing with poorly classified data from proprietary software with limited IFC capabilities. If you are reassigning a type, the occurrence classes are also reassigned to maintain validity. Vice versa, if you are reassigning an occurrence, the type is also reassigned in IFC4 and up. In IFC2X3, this may not occur if the type cannot be unambiguously derived, so you are required to manually check this. Reassigning type class to occurrence (and vice versa) is supported.

## Parameters

- **product** (`entity_instance`) : The IfcProduct that you want to change the class of.
- **ifc_class** (`str`) , default: `IfcBuildingElementProxy` : The new IFC class you want to change it to.
- **predefined_type** (`Optional[str]`) : In case you want to change the predefined type too. User defined types are also allowed, just type what you want.
- **occurrence_class** (`Optional[str]`) : IFC class to assign to occurrences in case if provided ``ifc_class`` is IfcTypeProduct. If omitted, class will be deduced automatically from the type. Only really needed in IFC2X3, since in IFC4+ there is no ambiguity on what class to assign to occurrences.
## Returns

The newly modified product.
