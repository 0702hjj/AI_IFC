# Model Tree & Property Inspection

## Model tree

The left panel shows the model tree organized by spatial structure (Site → Building → Storey → elements), built from the metadata exported by the converter:

- **Search**: filter by name or type.
- **Type filter**: filter elements by IFC type (e.g. IfcWall).
- **Visibility**: toggle visibility per node.
- **Locate**: clicking a node flies the camera to the element and highlights the selection.

## Property inspector

The right property panel shows the selected element's property sets (psets):

- Pset groups are collapsible; the first one is expanded by default.
- Property search and copy (written to the clipboard).
- Whitelisted fields (Name / Description / Classification / FireRating / Comments) can be edited inline and are saved as overrides with a modification marker; see [IFC Property Editing](/en/viewer/editing).

## Technical notes

The metadata is exported by the converter in xeokit's standard metamodel JSON; `metaObjects[].id` is the IFC GlobalId, identical to the XKT entity ids, so selection, coloring and diff results all align. For the schema see the metadata.json section of [Viewer REST API](/en/reference/rest-api).
