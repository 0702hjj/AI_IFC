# geometry.add_topology_representation

## API Definition

```python
def add_topology_representation(model, context: entity_instance, item: entity_instance, representation_identifier: Optional[str], representation_type: Optional[str]) -> entity_instance
```

*Source: api/geometry/add_topology_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_topology_representation", model, ...)`
- direct: `import ifcopenshell.api.geometry; ifcopenshell.api.geometry.add_topology_representation(model, ...)`

## Description

Adds an IfcTopologyRepresentation for a structural element

Structural analysis elements (IfcStructuralSurfaceMember, IfcStructuralCurveMember) use topology representations rather than solid geometry. This is analogous to :func:`add_axis_representation` and :func:`add_profile_representation` but produces an IfcTopologyRepresentation instead of an IfcShapeRepresentation. The representation type ("Face", "Edge", "Vertex") is inferred from the item's IFC class if not provided explicitly.

## Parameters

- **context** (`entity_instance`) : The IfcGeometricRepresentationContext for the representation, typically a Reference context.
- **item** (`entity_instance`) : The IfcTopologicalRepresentationItem (e.g. IfcFaceSurface, IfcEdge) to include in the representation.
- **representation_identifier** (`Optional[str]`) : The RepresentationIdentifier string. Defaults to the context's ContextIdentifier.
- **representation_type** (`Optional[str]`) : The RepresentationType string ("Face", "Edge", "Vertex"). Inferred from item class if not given.
## Returns

The newly created IfcTopologyRepresentation entity.
