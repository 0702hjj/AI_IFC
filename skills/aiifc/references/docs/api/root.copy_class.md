# root.copy_class

## API Definition

```python
def copy_class(model, product: entity_instance) -> entity_instance
```

*Source: api/root/copy_class*

## Import Surface

- run: `ifcopenshell.api.run("root.copy_class", model, ...)`
- direct: `import ifcopenshell.api.root; ifcopenshell.api.root.copy_class(model, ...)`

## Description

Copies a product

The following relationships are also duplicated: * The copy will have the same object placement coordinates as the original. * The copy will have duplicated property sets, properties, and quantities * The copy will have all nested distribution ports copied too * The copy will be part of the same aggregate * The copy will be contained in the same spatial structure * The copy, if it is an occurrence, will have the same type * Voids are duplicated too * The copy will have the same material as the original. Parametric material set usages will be copied. * The copy will be part of the same groups as the original. Be warned that: * Representations are _not_ copied. Copying representations is an expensive operation so for now the user is responsible for handling representations. * Filled voids are not copied, as there is no guarantee that the filling will also be copied. * Path connectivity is not copied, as there is no guarantee that the connections are still valid.

## Parameters

- **product** (`entity_instance`) : The IfcProduct to copy.
## Returns

The copied product
