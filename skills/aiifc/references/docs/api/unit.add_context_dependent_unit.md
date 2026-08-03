# unit.add_context_dependent_unit

## API Definition

```python
def add_context_dependent_unit(model, unit_type: str = USERDEFINED, name: str = THINGAMAJIG, dimensions: tuple[int, int, int, int, int, int, int] = (0, 0, 0, 0, 0, 0, 0)) -> entity_instance
```

*Source: api/unit/add_context_dependent_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.add_context_dependent_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.add_context_dependent_unit(model, ...)`

## Description

Add a new arbitrary unit that can only be interpreted in a project specific context

Occasionally the construction industry uses arbitrary units to quantify objects, like "pairs" of door hardware, "palettes" or "boxes" of fixings or equipment.

## Parameters

- **unit_type** (`str`) , default: `USERDEFINED` : Typically should be left as USERDEFINED, unless for some bizarre reason you are redefining something you could use a sensible normal unit for. In that case, firstly stop whatever you're doing and have a hard think about your life, and then if life really is going that badly for you, check out the IFC docs for IfcUnitEnum.
- **name** (`str`) , default: `THINGAMAJIG` : Give your unit a name. X what? X bananas?
- **dimensions** (`tuple[int, int, int, int, int, int, int]`) , default: `(0, 0, 0, 0, 0, 0, 0)` : Units typically measure one of 7 fundamental physical dimensions: length, mass, time, electric current, temperature, substance amount, or luminous intensity. These are represented as a list of 7 integers, representing the exponents of each one of these dimensions. For example, a length unit is (1, 0, 0, 0, 0, 0, 0), where as an area unit is (2, 0, 0, 0, 0, 0, 0). A unit of meters per second is (1, 0, -1, 0, 0, 0, 0). For context dependent units, it is recommended to leave this as the default of (0, 0, 0, 0, 0, 0, 0).
## Returns

The new IfcContextDependentUnit
