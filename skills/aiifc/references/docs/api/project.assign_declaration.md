# project.assign_declaration

## API Definition

```python
def assign_declaration(model, definitions: list[entity_instance], relating_context: entity_instance) -> Optional[entity_instance]
```

*Source: api/project/assign_declaration*

## Import Surface

- run: `ifcopenshell.api.run("project.assign_declaration", model, ...)`
- direct: `import ifcopenshell.api.project; ifcopenshell.api.project.assign_declaration(model, ...)`

## Description

Declares the list of elements to the project

Feature was added in IFC4. All data in a model must be directly or indirectly related to the project. Most data is indirectly related, existing instead within the spatial decomposition tree. Other data, such as types, may be declared at the top level. Most of the time, the API handles declaration automatically for you. There is one scenario where you might want to explicitly declare objects to the project, and that's when you want to organise objects into project libraries for future use (such as an assets library). Assigning a declaration lets you say that an object belongs to a library.

## Parameters

- **definitions** (`list[entity_instance]`) : The list of objects you want to declare. Typically a list of assets.
- **relating_context** (`entity_instance`) : The IfcProject, or more commonly the IfcProjectLibrary that you want the object to be part of.
## Returns

The new IfcRelDeclares relationship or None if all definitions were already declared / do not support declaration.
