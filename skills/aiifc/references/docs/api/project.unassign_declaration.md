# project.unassign_declaration

## API Definition

```python
def unassign_declaration(model, definitions: list[entity_instance], relating_context: entity_instance) -> None
```

*Source: api/project/unassign_declaration*

## Import Surface

- run: `ifcopenshell.api.run("project.unassign_declaration", model, ...)`
- direct: `import ifcopenshell.api.project; ifcopenshell.api.project.unassign_declaration(model, ...)`

## Description

Unassigns a list of objects from a project or project library

Typically used to remove an asset from a project library.

## Parameters

- **definitions** (`list[entity_instance]`) : The list of objects you want to undeclare. Typically a list of assets.
- **relating_context** (`entity_instance`) : The IfcProject, or more commonly the IfcProjectLibrary that you want the object to no longer be part of.
## Returns

None
