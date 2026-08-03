# pset.edit_pset

## API Definition

```python
def edit_pset(model, pset: entity_instance, name: Optional[str], properties: Optional[dict[str, Any]], pset_template: Optional[entity_instance], should_purge: bool = True) -> None
```

*Source: api/pset/edit_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.edit_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.edit_pset(model, ...)`

## Description

Edits a property set and its properties

At its simplest usage, this may be used to edit the name of a property set. It may also be used to add, edit, or remove properties, either arbitrarily or using a property set template. A list of properties are provided as a dictionary, where the keys are property names, and values are property values. Keys that don't already exist are interpreted as properties to be added. Keys that already exist are interpreted as properties to be edited. A "None" value may specify a property to be deleted. Properties must have a data type. There are lots of data types in IFCs, not just simple unitless data types like integers, booleans, text, but also distinguishing between types of text, like labels versus descriptive text. There are also lots of unit-based data types like areas, volumes, lengths, power, density, flow rates, pressure, etc. To ensure the appropriate data type is used for properties, a property set template may be used. These can be seen as "property specifications". A default selection is provided by buildingSMART, so that all buildingSMART defined standard properties have exactly the same data types and exactly the right property names without fear of invalid data or typos. The built-in buildingSMART templates are always loaded. However, you may also specify your own templates. If you try to add a non-standard property that does not exist in either your own template or in the built-in buildingSMART template, then you have the responsibility to ensure that data types are always consistent and correct.

## Parameters

- **pset** (`entity_instance`) : The IfcPropertySet to edit.
- **name** (`Optional[str]`) : A new name for the property set. If no name is specified, the property set name is not changed.
- **properties** (`Optional[dict[str, Any]]`) : A dictionary of properties. The keys must be a string of the name of the property. The data type of the value will be determined by the property set template. If no property set template is found, the data types of the Python values will influence the IFC data type of the property. String values will become IfcLabel, float values will become IfcReal, booleans will become IfcBoolean, and integers will become IfcInteger. If more control is desired, you may explicitly specify IFC data objects directly. Note that provided `properties` might be mutated in the process.
- **pset_template** (`Optional[entity_instance]`) : If a property set template is provided, this will be used to determine data types. If no user-defined template is provided, the built-in buildingSMART templates will be loaded.
- **should_purge** (`bool`) , default: `True` : If set as False, properties set to None will be left as None but not removed. If set to true, properties set to None will actually be removed. The default of true is the same behaviour as :func:`ifcopenshell.api.pset.edit_qto`.
## Returns

None
