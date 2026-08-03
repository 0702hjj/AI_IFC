# material.add_material

## API Definition

```python
def add_material(model, name: Optional[str], category: Optional[str], description: Optional[str]) -> entity_instance
```

*Source: api/material/add_material*

## Import Surface

- run: `ifcopenshell.api.run("material.add_material", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_material(model, ...)`

## Description

Adds a new material

A material in IFC represents a physical material, such as timber, steel, concrete, aluminium, etc. It may also contain physical properties used for structural or lighting simulation. Note that unlike the computer graphics industry, a material by itself does not define any colour or lighting information. Colours in IFC are known as "styles", and an IFC material may or may not have any style information associated with it. See ifcopenshell.api.style for more information. A material is typically given a code name which is used by architects in elevations and details when tagging finishes. Materials are also useful to structural engineers in specifying the exact types of concrete and steel to be used in structural simulations. In addition, materials can belong to a category. Specifying this category is critical to allow model recipients to make simple queries like "show me all concrete / steel" elements in the model. Without standardised category naming of all materials, this type of query becomes a bespoke and inefficient task. A list of categories are: 'concrete', 'steel', 'aluminium', 'block', 'brick', 'stone', 'wood', 'glass', 'gypsum', 'plastic', and 'earth'. The user is allowed to specify their own category instead if none of these categories are appropriate. Note that categories are not available in IFC2X3. This shortcoming is one of the big reasons projects should upgrade to IFC4. Additionally, a material's description provides more information beyond its name or category.

## Parameters

- **name** (`Optional[str]`) : The name of the material, typically tagged in a finishes drawing or schedule.
- **category** (`Optional[str]`) : The category of the material.
- **description** (`Optional[str]`) : A description of the material.
## Returns

The newly created IfcMaterial
