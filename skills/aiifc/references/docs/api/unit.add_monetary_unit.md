# unit.add_monetary_unit

## API Definition

```python
def add_monetary_unit(model, currency: str = DOLLARYDOO) -> entity_instance
```

*Source: api/unit/add_monetary_unit*

## Import Surface

- run: `ifcopenshell.api.run("unit.add_monetary_unit", model, ...)`
- direct: `import ifcopenshell.api.unit; ifcopenshell.api.unit.add_monetary_unit(model, ...)`

## Description

Add a new currency

Currency units are useful in cost plans to know in what currency the costs are calculated in. The currencies should follow ISO 4217, like USD, GBP, AUD, MYR, etc.

## Parameters

- **currency** (`str`) , default: `DOLLARYDOO` : The currency code
## Returns

The newly created IfcMonetaryUnit
