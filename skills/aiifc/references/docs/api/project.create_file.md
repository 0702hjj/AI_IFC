# project.create_file

## API Definition

```python
def create_file(model, version: Literal['IFC2X3', 'IFC4', 'IFC4X3'] = IFC4) -> file_path
```

*Source: api/project/create_file*

## Import Surface

- run: `ifcopenshell.api.run("project.create_file", model, ...)`
- direct: `import ifcopenshell.api.project; ifcopenshell.api.project.create_file(model, ...)`

## Description

Create a blank IFC model file object

Create a new IFC file object based on the nominated schema version. The schema version you choose determines what type of IFC data you can store in this model. The file is blank and contains no entities. It also sets up header data for STEP file serialisation, such as the current timestamp, IfcOpenShell as the preprocessor, and defaults to a DesignTransferView MVD.

## Parameters

- **version** (`Literal['IFC2X3', 'IFC4', 'IFC4X3']`) , default: `IFC4` : The schema version of the IFC file. Choose from "IFC2X3", "IFC4", or "IFC4X3". If you have loaded in a custom schema, you may specify that schema identifier here too.
## Returns

The created IFC file object.
