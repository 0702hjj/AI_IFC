# geometry.add_axis_representation

## API Definition

```python
def add_axis_representation(model, context: entity_instance, axis: tuple[tuple[float, float] | tuple[float, float, float], tuple[float, float] | tuple[float, float, float]]) -> entity_instance
```

*Source: api/geometry/add_axis_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_axis_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_axis_representation(model, ...)`

## Description

Adds a new axis representation

Certain objects are typically "axis-based", such as walls, beams, and columns. This means you can represent them abstractly by simply drawing a single line either in 2D (such as for walls) or 3D (for beams and columns). Humans can understand this axis-based representation as being a simplification of a layered extrusion or a profile that is being extruded along that axis and joined to other elements. Using an axis-based representation makes it easy for users and computers to analyse connectivity and spatial relationships, as well as makes it easy to parametrically edit these objects by simply stretching the start or end of the axis. For now, only simple straight line axes are supported, represented by a start and end coordinate. The order is important. For walls, the start must be at the minimum local X ordinate, and the end at the maximum local X ordinate. For beams and columns, the start is at the minimum local Z ordinate, and the end of the maximum local Z ordinate. The first coordinate is the "start" and the second coordinate is the "end". This stat and end is then used to determine any parametric junctions with other elements. Using an axis-representation is optional, but highly recommended for "standard" representations of walls, beams, columns, and other structural members. A rule of thumb is that if you can draw it as a line on paper, you can probably represent it using an axis.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext that the representation is part of. This must be either a Model/Axis/GRAPH_VIEW (3D) or Plan/Axis/GRAPH_VIEW (2D).
- **axis** (`tuple[tuple[float, float] | tuple[float, float, float], tuple[float, float] | tuple[float, float, float]]`) : The axis, as a list of two coordinates, the coordinates being either a list of 2 or 3 float coordinates depending on whether the axis is 2D or 3D.
## Returns

The newly created IfcShapeRepresentation entity
