# type.assign_type

## API Definition

```python
def assign_type(model, related_objects: list[entity_instance], relating_type: entity_instance, should_map_representations = True) -> Optional[entity_instance]
```

*Source: api/type/assign_type*

## Import Surface

- run: `ifcopenshell.api.run("type.assign_type", model, ...)`
- direct: `import ifcopenshell.api.type; ifcopenshell.api.type.assign_type(model, ...)`

## Description

Assigns a type to occurrences of an object

IFC supports the concept of occurrences and types. An occurrence is an actual physical product in the real world: like a wall, a chair, a door, a column, a pump, and so on. Most occurrences have a corresponding type. A type describes either a common shape and set of properties of a particular model of equipment, or a construction typology. An occurrence may only have zero or one type. For example, architects would typically have a door schedule for individual occurrences of doors and a door types schedule for a handful of door types, described by the door hardware, frame, and panel. Other examples might be window types or wall types. Structural engineers would have a list of column types, beam types, slab types, etc, such as a 400 diameter column, a 500 diameter column, and so on. Services consultant might nominate a particular type of sprinkler which have many occurrences, or light fixture types, and so on. Types are critical as they communicate to the procurement team what types of equipment and products need to be procured. The individual occurrences of that type tell them how many to procure. Types are also critical in construction as they indicate succinctly how to manufacture or construct something. For example, a wall type is enough information for a builder to understand the build up and construction of a wall. Types are used to help break down cost plans, or isolate portions of an assembly process for construction scheduling. Types are also used in facility maintenance, as occurrences sharing the same type can be repaired in the same way or by replacing the same parts. An occurrence of a type inherits all the properties and materials of the type. For example, a 2HR fire rated wall type implies that all wall occurrences of that wall type will also be 2HR fire rated. A type may or may not have a geometric representation. If a type does not have any representation, then the occurrences are free to have any representation of their own. However, if a type has a representation, all occurrences must have the same representation. For example, if a light fixture downlight type has a representation of a cylinder, then all occurrences must have exactly the same cylinder as its representation. If you change the cylinder's shape of the type, then all occurrence representations will also change. If a type does not have any geometric representation, they may have a parametric material representation. This may be either a parametric layered material or parametric cross-sectional profile material. If this is the case, the occurrence must be constructed out of the parametric material. For example, if a wall type uses a list of parametric layers indicating a thickness of 13mm plasterboard and 90mm stud, then the thickness of every wall occurrence representation must be 103mm. The length of each wall, however, may vary. Similarly, if a beam type has a parametric profile material of an I-beam, then all beam occurrences must also be this I-beam shape, though the length may vary. It is highly recommended for every occurrence to have a type. There are some exceptions to the rule, such as in heritage architecture or as-built or dilapidation models, where existing conditions are ambiguous, unknown or are so bespoke as to have no logical type.

## Parameters

- **related_objects** (`list[entity_instance]`) : The IfcElement occurrences.
- **relating_type** (`entity_instance`) : The IfcElementType type.
- **should_map_representations** , default: `True` : If a type has a representation map, IFC requires all occurrences to map those representations. Some IFC vendors might disobey this, or you might want to handle it yourusecase. In this scenario, you may set this to False. This also enabled adding material usages mapping.
## Returns

The IfcRelDefinesByType relationship or `None` if `related_objects` was empty list.
