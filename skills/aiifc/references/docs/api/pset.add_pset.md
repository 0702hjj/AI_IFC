# pset.add_pset

## API Definition

```python
def add_pset(model, product: entity_instance, name: str, ifc2x3_subclass: Optional[str]) -> entity_instance
```

*Source: api/pset/add_pset*

## Import Surface

- run: `ifcopenshell.api.run("pset.add_pset", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.add_pset(model, ...)`

## Description

Adds a new property set to a product

Products, such as physical objects or types in IFC may have properties associated with them. These properties are typically simple key value metadata with data types. For example, a wall type may have a property called FireRating with a text value of "2HR". Properties are grouped into property sets, so that related properties are grouped together. If a property is assigned to a type, the property is inherited by all occurrences of that type. For example, a wall type with a FireRating property of "2HR" automatically implies that all walls of that wall type also have a FireRating of "2HR". It is not necessary to explictly define the property again for each occurrence. This also means that properties are typically defined on types. If the same property is defined at an occurrence, this overrides the property defined on the type. buildingSMART has come up with a long list of standardised properties for the most common properties required internationally. This solves the age-old question of "where do I store my FireRating data for walls"? The answer, in this case, is in the "FireRating" property with an "IfcLabel" data type grouped in the "Pset_WallCommon" property set. It is recommended to view the list of standardised buildingSMART properties and see if any suit your needs first. If none are appropriate, then you are free to create your own custom properties. This function adds a blank named property set. One you have a property set you may add properties using ifcopenshell.api.pset.edit_pset. See also ifcopenshell.api.pset.add_qto if you want to add quantification data, rather than arbitrary metadata.

## Parameters

- **product** (`entity_instance`) : The IfcObject that you want to assign a property set to.
- **name** (`str`) : The name of the property set. Property sets that are standardised by buildingSMART typically have a prefix of "Pset_", like "Pset_WallCommon". If you create your own, you must not use that prefix. It is recommended to use your own prefix tailored to your project, company, or local government requirement.
- **ifc2x3_subclass** (`Optional[str]`) : IFC2X3 subclass for material or profile properties. In IFC2X3 IfcProfileProperties and IfcMaterialProperties are abstract so you need one of their subclasses to instantiate them. By default, for profile will be created IfcGeneralProfileProperties and for material - IfcExtendedMaterialProperties. Will have no effect in >=IFC4.
## Returns

The newly created IfcPropertySet
