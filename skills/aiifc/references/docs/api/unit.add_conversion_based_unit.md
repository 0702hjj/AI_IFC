# unit.add_conversion_based_unit

## API Definition

```python
def add_conversion_based_unit(model, name: str = foot, conversion_offset: Optional[float]) -> entity_instance
```

*Source: api/unit/add_conversion_based_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.add_conversion_based_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.add_conversion_based_unit(model, ...)`

## Description

Add a conversion based unit

If you're in one of those countries who don't use SI units, you're probably simply using SI units converted into another unit. If you want to use _those_ units, you can create a conversion based unit with this function. You can choose from one of: inch, foot, yard, mile, square inch, square foot, square yard, acre, square mile, cubic inch, cubic foot, cubic yard, litre, fluid ounce UK, fluid ounce US, pint UK, pint US, gallon UK, gallon US, degree, ounce, pound, ton UK, ton US, tonne, lbf, kip, psi, ksi, minute, hour, day, btu, and fahrenheit.

## Parameters

- **name** (`str`) , default: `foot` : A converted name chosen from the list above.
- **conversion_offset** (`Optional[float]`) : If you want to offset the conversion further by a set number, you may specify it here. For example, fahrenheit is 1.8 * kelvin - 459.67. The -459.67 is the conversion offset. Note that this is just an example and you don't actually need to specify that for fahrenheit as it's built into this API function. For advanced users only.
## Returns

The new IfcConversionBasedUnit or IfcConversionBasedUnitWithOffset
