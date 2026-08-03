# material.add_layer

## API Definition

```python
def add_layer(model, layer_set: entity_instance, material: entity_instance, name: Optional[str]) -> entity_instance
```

*Source: api/material/add_layer*

## Import Surface

- run: `ifcopenshell.api.run("material.add_layer", model, ...)`
- direct: `import ifcopenshell.api.material; ifcopenshell.api.material.add_layer(model, ...)`

## Description

Adds a new layer to a layer set

A layer represents a portion of material within a layered build up, defined by a thickness. Typical layered construction includes walls and slabs, where a wall might include a layer of finish, a layer of structure, a layer of insulation, and so on. It is recommended to define layered construction this way where it is unnecessary to define the exact geometry of how the wall or slab will be built, and it will instead be determined on site by a trade. Layers are defined in a particular order and thickness, so that it is clear which layer comes next.

## Parameters

- **layer_set** (`entity_instance`) : The IfcMaterialLayerSet that the layer is part of. The layer set represents a group of layers. See ifcopenshell.api.material.add_material_set for more information on how to add a layer set.
- **material** (`entity_instance`) : The IfcMaterial that the layer is made out of.
- **name** (`Optional[str]`) : An optional name of the layer.
## Returns

The newly created IfcMaterialLayer
