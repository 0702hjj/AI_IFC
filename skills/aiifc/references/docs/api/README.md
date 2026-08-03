# ifcopenshell.api Index

Generated docs for the core 12 packages of `ifcopenshell.api`, 103 usecases covering the full IFC authoring pipeline from project setup to property sets.

## Import Conventions

- **run** (recommended): `ifcopenshell.api.run("<package>.<usecase>", model, **kwargs)`
- **direct**: `import ifcopenshell.api.<package>; ifcopenshell.api.<package>.<usecase>(model, **kwargs)`

All parameters use **keyword arguments**. The first argument is always `model` (the IFC file object).

## Recommended Reading Order

Read categories top-to-bottom — this mirrors the skeleton-first pipeline (see MODELING_WORKFLOWS.md). Categories 1-3 build the mandatory skeleton; 4-6 add geometry; 7-9 attach data.

---

## 1. Project Setup

The mandatory foundation: create file, assign units, add geometric context.

- [project.create_file](project.create_file.md) — Create a blank IFC model file
- [project.append_asset](project.append_asset.md) — Append assets from another project
- [project.assign_declaration](project.assign_declaration.md) — Declare types in project library
- [project.unassign_declaration](project.unassign_declaration.md) — Undeclare types
- [unit.assign_unit](unit.assign_unit.md) — Assign default project units (mm/m²/m³)
- [unit.add_si_unit](unit.add_si_unit.md) — Add an SI unit (LENGTHUNIT, AREAUNIT, ...)
- [unit.add_conversion_based_unit](unit.add_conversion_based_unit.md) — Add conversion-based unit (e.g. DEGREE)
- [unit.add_context_dependent_unit](unit.add_context_dependent_unit.md) — Add context-dependent unit
- [unit.add_derived_unit](unit.add_derived_unit.md) — Add derived unit
- [unit.add_monetary_unit](unit.add_monetary_unit.md) — Add currency
- [unit.edit_named_unit](unit.edit_named_unit.md) — Edit a named unit
- [unit.edit_derived_unit](unit.edit_derived_unit.md) — Edit derived unit
- [unit.edit_monetary_unit](unit.edit_monetary_unit.md) — Edit currency
- [unit.remove_unit](unit.remove_unit.md) — Remove a unit
- [unit.unassign_unit](unit.unassign_unit.md) — Unassign units from project
- [context.add_context](context.add_context.md) — Add geometric context (Model/Body/MODEL_VIEW)
- [context.edit_context](context.edit_context.md) — Edit context parameters
- [context.remove_context](context.remove_context.md) — Remove a context

## 2. Spatial Structure

Build the mandatory hierarchy: Project → Site → Building → Storey. Then place elements into storeys.

- [aggregate.assign_object](aggregate.assign_object.md) — Aggregate children into parent (spatial tree)
- [aggregate.unassign_object](aggregate.unassign_object.md) — Remove aggregation
- [spatial.assign_container](spatial.assign_container.md) — Place elements into a spatial container (element → Storey)
- [spatial.unassign_container](spatial.unassign_container.md) — Remove element from container
- [spatial.reference_structure](spatial.reference_structure.md) — Reference a spatial structure
- [spatial.dereference_structure](spatial.dereference_structure.md) — Remove spatial reference

## 3. Entity Lifecycle

Create, copy, reassign, or remove any IFC product (walls, doors, slabs, types, ...).

- [root.create_entity](root.create_entity.md) — Create any IFC entity (IfcWall, IfcDoor, IfcProject, ...)
- [root.copy_class](root.copy_class.md) — Copy an entity with its data
- [root.reassign_class](root.reassign_class.md) — Change entity class (e.g. IfcWall → IfcWallStandardCase)
- [root.remove_product](root.remove_product.md) — Remove a product and clean up relationships
- [type.assign_type](type.assign_type.md) — Assign a type to element occurrences (IfcWallType → IfcWall)
- [type.map_type_representations](type.map_type_representations.md) — Map representations from type to occurrences
- [type.unassign_type](type.unassign_type.md) — Remove type assignment

## 4. Wall Geometry

Parametric wall representations and two-point wall creation.

- [geometry.add_wall_representation](geometry.add_wall_representation.md) — Add wall body (length/height/thickness)
- [geometry.create_2pt_wall](geometry.create_2pt_wall.md) — Create wall between two points
- [geometry.regenerate_wall_representation](geometry.regenerate_wall_representation.md) — Regenerate wall body after connections
- [geometry.add_railing_representation](geometry.add_railing_representation.md) — Add railing representation

## 5. Slab & Profile Geometry

Slab representations and arbitrary/parameterized cross-section profiles.

- [geometry.add_slab_representation](geometry.add_slab_representation.md) — Add slab body (length/width/depth/offset)
- [geometry.add_profile_representation](geometry.add_profile_representation.md) — Add profile-based body (profile + extrusion depth)
- [profile.add_arbitrary_profile](profile.add_arbitrary_profile.md) — Define arbitrary closed profile (from coordinates/shapely)
- [profile.add_arbitrary_profile_with_voids](profile.add_arbitrary_profile_with_voids.md) — Arbitrary profile with inner voids
- [profile.add_parameterized_profile](profile.add_parameterized_profile.md) — Define parameterized profile (rectangle/circle/I-section/...)
- [profile.copy_profile](profile.copy_profile.md) — Copy a profile definition
- [profile.edit_profile](profile.edit_profile.md) — Edit profile parameters
- [profile.remove_profile](profile.remove_profile.md) — Remove a profile

## 6. Door & Window Geometry

- [geometry.add_door_representation](geometry.add_door_representation.md) — Add door body (lining/panel dimensions)
- [geometry.add_window_representation](geometry.add_window_representation.md) — Add window body

## 7. Placement

Position elements relative to their container (Storey). ObjectPlacement forms a parent-child chain.

- [geometry.edit_object_placement](geometry.edit_object_placement.md) — Set element placement via 4x4 matrix (relative to parent)

## 8. Representation Management

Assign, copy, map, or remove shape representations on products.

- [geometry.assign_representation](geometry.assign_representation.md) — Assign a representation to a product
- [geometry.unassign_representation](geometry.unassign_representation.md) — Unassign representation
- [geometry.copy_representation](geometry.copy_representation.md) — Copy representation between elements
- [geometry.map_representation](geometry.map_representation.md) — Map representation via IfcRepresentationMap
- [geometry.remove_representation](geometry.remove_representation.md) — Remove a representation
- [geometry.add_shape_aspect](geometry.add_shape_aspect.md) — Add shape aspect for multi-material
- [geometry.validate_type](geometry.validate_type.md) — Validate type geometry compatibility

## 9. Openings & Fillings

Cut openings in walls/slabs and fill them with doors/windows.

- [feature.add_feature](feature.add_feature.md) — Create opening/projection in an element (IfcRelVoidsElement)
- [feature.add_filling](feature.add_filling.md) — Fill an opening with a door/window (IfcRelFillsElement)
- [feature.remove_feature](feature.remove_feature.md) — Remove an opening
- [feature.remove_filling](feature.remove_filling.md) — Remove a filling relationship

## 10. Boolean & Clipping

Boolean operations and half-space clipping on solids.

- [geometry.add_boolean](geometry.add_boolean.md) — Add boolean operation (union/cut/intersect)
- [geometry.remove_boolean](geometry.remove_boolean.md) — Remove a boolean result
- [geometry.clip_solid](geometry.clip_solid.md) — Clip solid with a half-space plane
- [geometry.clip_solid_bounded](geometry.clip_solid_bounded.md) — Clip solid with polygonally bounded half-space

## 11. Element Connections

Connect walls, paths, and elements semantically (for path-based topology).

- [geometry.connect_wall](geometry.connect_wall.md) — Connect two walls at an endpoint
- [geometry.connect_element](geometry.connect_element.md) — Connect two elements
- [geometry.connect_path](geometry.connect_path.md) — Connect path elements
- [geometry.disconnect_element](geometry.disconnect_element.md) — Disconnect elements
- [geometry.disconnect_path](geometry.disconnect_path.md) — Disconnect path elements

## 12. Other Representations

Specialized representations for specific use cases.

- [geometry.add_mesh_representation](geometry.add_mesh_representation.md) — Add tessellated mesh (vertices + faces)
- [geometry.add_axis_representation](geometry.add_axis_representation.md) — Add 2D axis (for parametric walls)
- [geometry.add_footprint_representation](geometry.add_footprint_representation.md) — Add footprint (for site/building)
- [geometry.add_topology_representation](geometry.add_topology_representation.md) — Add topology (vertices/edges/faces)
- [geometry.add_window_representation](geometry.add_window_representation.md) — (listed in category 6)

## 13. Materials

Material definitions: single material, layer sets (walls), profile sets (beams/columns), constituents.

- [material.assign_material](material.assign_material.md) — Assign material/layer-set/profile-set to element or type
- [material.unassign_material](material.unassign_material.md) — Remove material assignment
- [material.add_material](material.add_material.md) — Create a material definition
- [material.copy_material](material.copy_material.md) — Copy material
- [material.edit_material](material.edit_material.md) — Edit material attributes
- [material.remove_material](material.remove_material.md) — Remove material
- [material.add_material_set](material.add_material_set.md) — Create layer set / profile set / constituent set
- [material.remove_material_set](material.remove_material_set.md) — Remove material set
- [material.add_layer](material.add_layer.md) — Add layer to layer set (walls)
- [material.edit_layer](material.edit_layer.md) — Edit layer thickness/material
- [material.edit_layer_usage](material.edit_layer_usage.md) — Edit layer usage (offset/sense)
- [material.remove_layer](material.remove_layer.md) — Remove layer
- [material.add_profile](material.add_profile.md) — Add profile to profile set (beams/columns)
- [material.edit_profile](material.edit_profile.md) — Edit profile in set
- [material.edit_profile_usage](material.edit_profile_usage.md) — Edit profile usage
- [material.assign_profile](material.assign_profile.md) — Assign profile to element
- [material.remove_profile](material.remove_profile.md) — Remove profile from set
- [material.add_constituent](material.add_constituent.md) — Add constituent to constituent set
- [material.edit_constituent](material.edit_constituent.md) — Edit constituent
- [material.remove_constituent](material.remove_constituent.md) — Remove constituent
- [material.add_list_item](material.add_list_item.md) — Add list item to material set
- [material.remove_list_item](material.remove_list_item.md) — Remove list item
- [material.reorder_set_item](material.reorder_set_item.md) — Reorder items in set
- [material.set_shape_aspect_constituents](material.set_shape_aspect_constituents.md) — Set shape aspect constituents
- [material.edit_assigned_material](material.edit_assigned_material.md) — Edit assigned material usage

## 14. Property Sets & Quantities

Attach Pset (designer-specified properties) and Qto (geometry-derived quantities).

- [pset.add_pset](pset.add_pset.md) — Add property set to element (e.g. Pset_WallCommon)
- [pset.edit_pset](pset.edit_pset.md) — Edit property values in a pset
- [pset.remove_pset](pset.remove_pset.md) — Remove a pset from element
- [pset.assign_pset](pset.assign_pset.md) — Assign existing pset to elements
- [pset.unassign_pset](pset.unassign_pset.md) — Unassign pset from elements
- [pset.unshare_pset](pset.unshare_pset.md) — Copy shared pset as element-specific
- [pset.add_qto](pset.add_qto.md) — Add quantity set (e.g. Qto_WallBaseQuantities)
- [pset.edit_qto](pset.edit_qto.md) — Edit quantity values
