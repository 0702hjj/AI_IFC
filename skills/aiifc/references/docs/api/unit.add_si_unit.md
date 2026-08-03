# unit.add_si_unit

## API Definition

```python
def add_si_unit(model, unit_type: str = LENGTHUNIT, prefix: Optional[str]) -> entity_instance
```

*Source: api/unit/add_si_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.add_si_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.add_si_unit(model, ...)`

## Description

Add a new SI unit

The supported types are ABSORBEDDOSEUNIT, AMOUNTOFSUBSTANCEUNIT, AREAUNIT, DOSEEQUIVALENTUNIT, ELECTRICCAPACITANCEUNIT, ELECTRICCHARGEUNIT, ELECTRICCONDUCTANCEUNIT, ELECTRICCURRENTUNIT, ELECTRICRESISTANCEUNIT, ELECTRICVOLTAGEUNIT, ENERGYUNIT, FORCEUNIT, FREQUENCYUNIT, ILLUMINANCEUNIT, INDUCTANCEUNIT, LENGTHUNIT, LUMINOUSFLUXUNIT, LUMINOUSINTENSITYUNIT, MAGNETICFLUXDENSITYUNIT, MAGNETICFLUXUNIT, MASSUNIT, PLANEANGLEUNIT, POWERUNIT, PRESSUREUNIT, RADIOACTIVITYUNIT, SOLIDANGLEUNIT, THERMODYNAMICTEMPERATUREUNIT, TIMEUNIT, VOLUMEUNIT. Prefixes supported are ATTO, CENTI, DECA, DECI, EXA, FEMTO, GIGA, HECTO, KILO, MEGA, MICRO, MILLI, NANO, PETA, PICO, TERA.

## Parameters

- **unit_type** (`str`) , default: `LENGTHUNIT` : A type of unit chosen from the list above. For example, choosing LENGTHUNIT will give you a metre.
- **prefix** (`Optional[str]`) : A prefix chosen from the list above, or None for no prefix.
## Returns

The newly created IfcSIUnit
