# profile.add_parameterized_profile

## API Definition

```python
def add_parameterized_profile(model, ifc_class: str, profile_type: str = AREA) -> entity_instance
```

*Source: api/profile/add_parameterized_profile*

## Import Surface

- run: `ifcopenshell.api.run("profile.add_parameterized_profile", model, ...)`
- direct: `import ifcopenshell.api.profile; ifcopenshell.api.profile.add_parameterized_profile(model, ...)`

## Description

Adds a new parameterised profile

IFC offers parameterised profiles for common standardised hot roll steel sections and common concrete forms. A full list is available on the IFC documentation as subclasses of IfcParameterizedProfileDef. Currently, this API has no benefit over directly calling ifcopenshell.file.create_entity.

## Parameters

- **ifc_class** (`str`) : The subclass of IfcParameterizedProfileDef that you'd like to create.
- **profile_type** (`str`) , default: `AREA`
## Returns

The newly created element depending on the specified ifc_class.
