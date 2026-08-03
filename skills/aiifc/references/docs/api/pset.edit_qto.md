# pset.edit_qto

## API Definition

```python
def edit_qto(model, qto: entity_instance, name: Optional[str], properties: Optional[dict[str, entity_instance | float | int | dict[str, entity_instance | float | int | dict[str, ForwardRef('PROP_VALUE_TYPE')]]]], pset_template: Optional[entity_instance]) -> None
```

*Source: api/pset/edit_qto*

## Import Surface

- run: `ifcopenshell.api.run("pset.edit_qto", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.edit_qto(model, ...)`

## Description

Edits a quantity set and its quantities

At its simplest usage, this may be used to edit the name of a quantity set. It may also be used to add, edit, or remove quantities. See ifcopenshell.api.pset.edit_pset for documentation on how this is intended to be used. One major difference is that quantities set to None are always purged. It is not allowed to have None quantities in IFC.

## Parameters

- **qto** (`entity_instance`) : The IfcElementQuantity or IfcPhysicalComplexQuantity to edit.
- **name** (`Optional[str]`) : A new name for the quantity set. If no name is specified, the quantity set name is not changed.
- **properties** (`Optional[dict[str, entity_instance | float | int | dict[str, entity_instance | float | int | dict[str, ForwardRef('PROP_VALUE_TYPE')]]]]`) : A dictionary of properties. The keys must be a string of the name of the quantity. The data type of the value will be determined by the quantity set template. If no quantity set template is found, the data types of the Python values and properties names will influence the IFC data type of the quantity.
- **pset_template** (`Optional[entity_instance]`) : If a quantity set template is provided, this will be used to determine data types. If no user-defined template is provided, the built-in buildingSMART templates will be loaded.
## Returns

None
