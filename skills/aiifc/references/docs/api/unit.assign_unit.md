# unit.assign_unit

## API Definition

```python
def assign_unit(model, units: Optional[list[entity_instance]], length: Optional[dict], area: Optional[dict], volume: Optional[dict]) -> entity_instance
```

*Source: api/unit/assign_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.assign_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.assign_unit(model, ...)`

## Description

Assign default project units

Whenever a unitised quantity is specified, such as a length, area, voltage, pressure, etc, these project units are used by default. It is also possible to override units for specific properties. For example, generally you might want square metres for area measurements, but you might want square millimeters for the measurements of the cross sectional area of cables in cable trays. However, this function only deals with the default project units.

## Parameters

- **units** (`Optional[list[entity_instance]]`) : A list of units to assign as project defaults. See ifcopenshell.api.unit.add_si_unit, unit.add_conversion_based_unit, and unit.add_monetary_unit for information on how to create units.
- **length** (`Optional[dict]`)
- **area** (`Optional[dict]`)
- **volume** (`Optional[dict]`)
## Returns

The IfcUnitAssignment element
