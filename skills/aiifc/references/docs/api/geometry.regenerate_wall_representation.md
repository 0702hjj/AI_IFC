# geometry.regenerate_wall_representation

## API Definition

```python
def regenerate_wall_representation(model, wall: entity_instance, length: float = 1.0, height: float = 1.0, angle: Optional[float]) -> entity_instance
```

*Source: api/geometry/regenerate_wall_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.regenerate_wall_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.regenerate_wall_representation(model, ...)`

## Description

Regenerate the body representation of a wall taking into account connections.

IFC defines how a standard (case) wall should behave that has a material layer set and connections to other walls using IfcRelConnectsPathElements. This function will regenerate the body geometry of a wall taking into account the notches, butts, mitres, etc in the wall due to connections with other walls. A standard wall has a 2D axis line as well as parameters defined in terms of layer thicknesses and priorities. The body geometry is defined as a 2D XY profile which is extruded in the +Z direction. For this function to work, a wall must have these defined and the project must have an axis and body representation context. For non-sloped walls, a 2D profile is generated and extruded in the +Z direction. The profile may be a composite profile, if the wall is split due to wall joins along the path of the wall that protrude all the way through the wall. For sloped walls, a basic rectangular 2D profile is extruded, and then additional extrusions are generated for each connection that boolean difference the base extrusion. Clippings applied via :func:`geometry.clip_solid` or :func:`geometry.clip_solid_bounded` are preserved only if the ``element`` parameter was passed when creating them, which registers the result in the ``BBIM_Boolean`` property set. Clippings created without that parameter are silently discarded during regeneration. This will also update the axis line representation (e.g. trim the axis line to any connections). The wall's object placement will also be updated such that the placement is equivalent to the axis line's start point (which therefore becomes (0.0, 0.0)). This is a logical, consistent, and useful placement coordinate (especially for apps that can pivot using this point). All this functionality relies on the Plan/Axis/GRAPH_VIEW representation context. It will be created if it does not exist.

## Parameters

- **wall** (`entity_instance`) : The IfcWall for the representation, only Model/Body/MODEL_VIEW type of representations are currently supported.
- **length** (`float`) , default: `1.0` : If the wall doesn't have an axis length, this is the default length in SI units.
- **height** (`float`) , default: `1.0` : If the wall doesn't already have a height, this is the default height in SI units.
- **angle** (`Optional[float]`) : If the wall doesn't already have a slope, this is the default angle in radians. Left as none or 0 defines no slope.
## Returns

The newly generated body IfcShapeRepresentation
