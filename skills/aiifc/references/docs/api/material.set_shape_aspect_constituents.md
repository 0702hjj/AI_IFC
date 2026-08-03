# material.set_shape_aspect_constituents

## API Definition

```python
def set_shape_aspect_constituents(model, element: entity_instance, context: entity_instance, materials: dict[str, entity_instance]) -> None
```

*Source: api/material/set_shape_aspect_constituents*

## Import Surface

- run: `ifcopenshell.api.run("material.set_shape_aspect_constituents", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.set_shape_aspect_constituents(model, ...)`

## Description

Assigns a material constituent set and sets styles based on shape aspects

An IFC element may be assigned to a set of material constituents. For example, a window may have a framing material and a glazing material. Each constituent may have a name, such as "Framing" (which may be assigned to an "Aluminium" material), and "Glazing" (assigned to a "Laminated Low-e Glass" material). An IFC element's geometry may be composed of multiple geometric items. These geometric items may have names, known as "Shape Aspects". For example a solid extrusion for the framing named "Framing" and a solid extrusion for the glass panel named "Glazing". A material may be associated with a style (i.e. colour). For example, a grey style for the "Aluminium" material and a transparent blue style for the "Laminated Low-e Glass" material. These three concepts of material constituents, shape aspects, and associated styles are correlated. For example, if the name (e.g. "Framing") of a material constituent and a shape aspect correlate, that means that the geometric item inherits the style (i.e. grey). This function lets you specify named material constituents, and it'll create a constituent set assigned to the element with those names. It'll then find any geometric representation items with shape aspects matching those names, and assign the correlating style. If an assigned material constituent set already exists matching those values, it will be reused. If the values do not match, the existing material constituent set will be removed if it is not used by anything else.

## Parameters

- **element** (`entity_instance`) : The IfcProduct or IfcTypeProduct
- **context** (`entity_instance`) : The IfcGeometricRepresentationContext, typically the body context. You can get this via :func:`ifcopenshell.util.representation.get_context`.
- **materials** (`dict[str, entity_instance]`) : The key is the name of the constituent, and the value is the IfcMaterial.
## Returns

None
