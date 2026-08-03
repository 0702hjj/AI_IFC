# pset.add_qto

## API Definition

```python
def add_qto(model, product: entity_instance, name: str) -> entity_instance
```

*Source: api/pset/add_qto*

## Import Surface

- run: `ifcopenshell.api.run("pset.add_qto", model, ...)`
- direct: `import ifcopenshell.api.pset; ifcopenshell.api.pset.add_qto(model, ...)`

## Description

Adds a new quantity set to a product

Products, such as physical objects or types in IFC may have quantities associated with them. These quantities are typically simple key value metadata with data types. For example, a wall type may have a quantity called NetSideArea with a area value of "4.2". Quantities are grouped into quantity sets, so that related quantities are grouped together. Quantities are similar to, but different from properties in that they may store a method of measurement or formula. Quantities may also have parametric relationships to other calculated values, such as cost schedules, resource utilisation, or construction task durations. buildingSMART has come up with a long list of standardised quantities for the most common quantities required internationally. This solves the age-old question of "what's the standard way of storing quantity take-off data"? It is recommended to view the list of standardised buildingSMART quantities and see if any suit your needs first. If none are appropriate, then you are free to create your own custom quantities. This function adds a blank named quantity set. One you have a quantity set you may add quantities using ifcopenshell.api.pset.edit_qto. See also ifcopenshell.api.pset.add_qto if you want to arbitrary metadata, rather than quantification data.

## Parameters

- **product** (`entity_instance`) : The IfcObject that you want to assign a quantity set to.
- **name** (`str`) : The name of the quantity set. Quantity sets that are standardised by buildingSMART typically have a prefix of "Qto_", like "Qto_WallBaseQuantities". If you create your own, you must not use that prefix. It is recommended to use your own prefix tailored to your project, company, or local government requirement.
## Returns

The newly created IfcElementQuantity
