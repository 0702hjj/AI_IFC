# feature.add_feature

## API Definition

```python
def add_feature(model, feature: entity_instance, element: entity_instance) -> entity_instance
```

*Source: api/feature/add_feature*

## Import Surface

- run: `ifcopenshell.api.run("feature.add_feature", model, ...)`
- direct: `import ifcopenshell.api.feature; ifcopenshell.api.feature.add_feature(model, ...)`

## Description

Create a projecting, voiding, or surface feature in an element

There are three main types of features: those that add, remove, or influence geometry of a parent object. The most common of these is an opening. For example, it is often necessary to cut out openings in elements like walls and slabs to make space to insert doors, windows, and other services that go through these penetrations. Whereas it is possible to simply draw the wall as a rectangle with a hole in it for the opening, often these openings have specific meanings. For example, an opening might be filled with a window, and so when the window moves, the opening should move with it. Alternatively, the opening itself might have fire or acoustic requirements, such that any service or equipment passing through that space must also comply with those requirements. For these types of semantic openings, you should have a distinct opening element which voids your regular element. For example, your wall will still be a rectangular prism with no hole in it, and a separate opening element will have a box representing the extents of the opening for a window. The opening element will automatically perform a geometric boolean operation to cut out the wall's geometry. Whenever you have an opening in you project, you should determine whether or not the opening is semantic (i.e. should be represented by a distinct opening object) or non-semantic (i.e. should simply be booleaned or be part of the shape of the object).

## Parameters

- **feature** (`entity_instance`) : The IfcFeatureElement to affect the element.
- **element** (`entity_instance`) : The IfcElement to add the feature to.
## Returns

The new IfcRelVoidsElement relationship
