# context.add_context

## API Definition

```python
def add_context(model, context_type: Optional[Literal['Model', 'Plan', 'NotDefined']], context_identifier: Optional[Literal['CoG', 'Box', 'Annotation', 'Axis', 'FootPrint', 'Profile', 'Surface', 'Reference', 'Body', 'Body-Fallback', 'Clearance', 'Lighting']], target_view: Optional[Literal['ELEVATION_VIEW', 'GRAPH_VIEW', 'MODEL_VIEW', 'PLAN_VIEW', 'REFLECTED_PLAN_VIEW', 'SECTION_VIEW', 'SKETCH_VIEW', 'USERDEFINED', 'NOTDEFINED']], target_scale: Optional[float], parent: Optional[entity_instance]) -> entity_instance
```

*Source: api/context/add_context*

## Import Surface

- run: `ifcopenshell.api.run("context.add_context", model, ...)`
- direct: `import ifcopenshell.api.context; ifcopenshell.api.context.add_context(model, ...)`

## Description

Adds a new geometric representation context

In IFC, physical objects may have zero, one, or multiple geometric representations associated with it. For example, a building storey might not have any geometry, but simply be a coordinate in space. Alternatively, a wall might have a 3D body representation in the form of a cuboid. As a final example, a door might also have a 3D body representation of a 3D door panel and door frame, but may additionally have a 2D door plan view representation of the door swing, and even a 2D elevation view of the door, a 3D box representing the disabled clearance zone of the door, a 2D profile representing the profile of the door to cut out in a wall, and so on. In this situation, a door will have multiple geometric representations. To distinguish between the different purposes of multiple geometric representations, each geometric representation must belong to a geometric representation "context". There are typically always 2 contexts, one for 3D representations and one for 2D representations. These 2 contexts then have subcontexts for things like the 3D body representation, clearance representations, annotation representations, and so on. Each representation of a physical IFC product (e.g. a door) must be assigned to one of these subcontexts. Therefore setting up appropriate contexts is critical prior to authoring any IFC model which contains geometry. There are two steps to setting up appropriate subcontexts. First, a 2D and/or 3D context must be added. These must be always called the "Model" context for 3D and the "Plan" context for 2D (even if the 2D geometry is not a plan view). Then, one or more subcontexts are added using either the "Model" or "Plan" as their parent. These subcontexts are further distinguished using an "identifier" and "target view". The "identifier" describes the purpose of the representation, and the "target view" describes the typical diagrammatic presentation that context's geometry should be viewed in. The most common identifiers you might use are: - Body: for the actual shape of the object - Box: the bounding box of the object (useful for shape analytics) - Axis: the parametric line determining the shape of the object - Profile: the elevation silhouette of the object, useful for cutting out holes for the object to fit into host elements - Footprint: the plan view silhouette of the object, useful for certain quantity take-off rules - Clearance: the clearance zone of the object - Annotation: symbolic annotations typically used in diagrams or drawings The most common "target views" you might use are: - MODEL_VIEW: for 3D geometry you might see in a BIM viewer - PLAN_VIEW: for 2D geometry you might see in a plan representation - ELEVATION_VIEW: for 2D geometry you might see in an elevation representation - SECTION_VIEW: for 2D geometry you might see in a section representation - GRAPH_VIEW: for 2D or 3D line or frame or path connectivity diagrams you might use for structural frame analysis, axis-based parametric modeling - SKETCH_VIEW: for viewing abstract high-level representations such as in bubble diagrams of spatial topology This may sound like a lot, but after a few typical contexts are set up at the beginning, it becomes easy to navigate and isolate geometry for different purposes. There is also the concept of a target scale, which represents the zoom level detail of geometry, but this is not currently supported by this API. Setting up all these contexts are also optional, and you may only use a single Model context and Body subcontext for simple models, but this simplification sacrifices the ability of more parametric or analytical usecases.

## Parameters

- **context_type** (`Optional[Literal['Model', 'Plan', 'NotDefined']]`) : The type of the context, must be one of "Model" or "Plan" only.
- **context_identifier** (`Optional[Literal['CoG', 'Box', 'Annotation', 'Axis', 'FootPrint', 'Profile', 'Surface', 'Reference', 'Body', 'Body-Fallback', 'Clearance', 'Lighting']]`) : The identifier of the context, chosen from one of the common identifiers above or consult the IFC documentation (under the IfcShapeRepresentation page) for more details. Optional for contexts, but mandatory for subcontexts.
- **target_view** (`Optional[Literal['ELEVATION_VIEW', 'GRAPH_VIEW', 'MODEL_VIEW', 'PLAN_VIEW', 'REFLECTED_PLAN_VIEW', 'SECTION_VIEW', 'SKETCH_VIEW', 'USERDEFINED', 'NOTDEFINED']]`) : the target view of the context, chosen from one of the common target views above or consult the IFC documentation (under the IfcShapeRepresentation page) for more details. Optional for contexts, but mandatory for subcontexts.
- **target_scale** (`Optional[float]`) : It defines the intended scale at which the representation is designed to be viewed or printed
- **parent** (`Optional[entity_instance]`) : the parent context. Must be left as None (the default) for contexts, and only set for subcontexts. Note that there are only contexts and subcontexts, a subcontext cannot have any children.
## Returns

the newly created IfcGeometricRepresentationContext or IfcGeometricRepresentationSubContext entity
