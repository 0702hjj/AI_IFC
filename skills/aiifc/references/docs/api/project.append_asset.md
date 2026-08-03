# project.append_asset

## API Definition

```python
def append_asset(model, library: file_path, element: entity_instance, reuse_identities: Optional[dict[int, entity_instance]], assume_asset_uniqueness_by_name: bool = True) -> entity_instance
```

*Source: api/project/append_asset*

## Import Surface

- run: `ifcopenshell.api.run("project.append_asset", model, ...)`
- direct: `import ifcopenshell.api.project; ifcopenshell.api.project.append_asset(model, ...)`

## Description

Appends an asset from a library into the active project

A BIM library asset may be a type product (e.g. wall type), product (e.g. pump), material, profile, or cost schedule. This copies the asset from the specified library file into the active project. It handles all details like ensuring that product materials, styles, properties, quantities, and so on are preserved. If an asset contains geometry, the geometric contexts are also intelligentely transplanted such that existing equivalent contexts are reused. Do not mix units.

## Parameters

- **library** (`file_path`) : The file object containing the asset.
- **element** (`entity_instance`) : An element in the library file of the asset. It may be an IfcTypeProduct, IfcProduct, IfcMaterial, IfcCostSchedule, or IfcProfileDef.
- **reuse_identities** (`Optional[dict[int, entity_instance]]`) : Optional dictionary of mapped entities' identities to the already created elements. It will be used to avoid creating duplicated inverse elements during multiple `project.append_asset` calls. If you want to add just 1 asset or if added assets won't have any shared elements, then it can be left empty.
- **assume_asset_uniqueness_by_name** (`bool`) , default: `True` : If True, checks if elements (profiles, materials, styles) with the same name already exist in the project and reuses them instead of appending new ones.
## Returns

The appended element
