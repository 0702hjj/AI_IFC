# ifcopenshell.api SDK Overview

ifcopenshell.api is the high-level IFC authoring API from IfcOpenShell. 12 core packages, 103 usecases, covering the full pipeline from project setup to property sets.

This document is the skill's "mental map" — connecting all packages, usecases, and IfcRel* relationships into a coherent whole. Use it to go from "what to build" to "which usecase to call".

## Mental Model

IFC model = **Spatial Tree** + **Elements** + **Geometry** + **Data**, built in skeleton-first deterministic order:

```
Spatial Tree (must build first, Wrapping phase)
  IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey
  (IfcRelAggregates links each level)

Elements (attached to skeleton, Layout phase)
  IfcWall / IfcDoor / IfcWindow / IfcSlab / IfcBeam / IfcColumn
  (IfcRelContainedInSpatialStructure links to Storey)

Geometry (3D Construction phase)
  IfcExtrudedAreaSolid (swept solid) / IfcArbitraryClosedProfileDef (arbitrary profile)
  (IfcShapeRepresentation → IfcProductDefinitionShape → Element)

Data (3D Construction phase)
  IfcPropertySet (Pset) / IfcElementQuantity (Qto) / IfcMaterial
  (IfcRelDefinesByProperties / IfcRelAssociatesMaterial links to Element)
```

**Relationships are explicit**: elements have no foreign keys or references. All connections are made through IfcRel* relationship entities, which are auto-created by the corresponding usecase. The agent never writes IfcRel* manually.

## Package Map

12 packages grouped by pipeline stage:

### Group 1: Skeleton (must build first)

| Package | Usecases | Core Usecase | Purpose |
|---|---|---|---|
| `project` | 4 | `create_file` | Create blank IFC file |
| `unit` | 11 | `assign_unit` | Assign metric units (mm/m²/m³) |
| `context` | 3 | `add_context` | Add geometric context (Model/Body/MODEL_VIEW) |
| `aggregate` | 2 | `assign_object` | Spatial aggregation (Project→Site→Building→Storey) |
| `spatial` | 4 | `assign_container` | Place elements into spatial container (Storey) |

### Group 2: Elements (attach to skeleton)

| Package | Usecases | Core Usecase | Purpose |
|---|---|---|---|
| `root` | 4 | `create_entity` | Create any IFC entity (wall/door/window/slab/type) |
| `type` | 3 | `assign_type` | Assign type to element occurrences (IfcWallType → IfcWall) |

### Group 3: Geometry (3D Construction)

| Package | Usecases | Core Usecase | Purpose |
|---|---|---|---|
| `geometry` | 30 | `add_wall_representation` / `edit_object_placement` / `assign_representation` / `create_2pt_wall` | Wall/slab/door/window geometry + placement |
| `profile` | 6 | `add_arbitrary_profile` / `add_parameterized_profile` | Arbitrary profile / parameterized cross-section |
| `feature` | 4 | `add_feature` / `add_filling` | Opening creation + door/window filling |

### Group 4: Data (3D Construction)

| Package | Usecases | Core Usecase | Purpose |
|---|---|---|---|
| `material` | 25 | `assign_material` / `add_layer` / `add_material_set` | Material (layer set/profile set/single) |
| `pset` | 8 | `add_pset` / `edit_pset` / `add_qto` | Property sets + quantities |

## Entity-Relationship Model

The agent needs to understand 7 IfcRel* types, all auto-created by usecases:

| IfcRel* | Meaning | Created by |
|---|---|---|
| IfcRelAggregates | A contains B (spatial tree) | `aggregate.assign_object` |
| IfcRelContainedInSpatialStructure | Element located in storey | `spatial.assign_container` |
| IfcRelDefinesByType | Type → occurrence | `type.assign_type` |
| IfcRelDefinesByProperties | Pset/Qto → element | `pset.add_pset` |
| IfcRelAssociatesMaterial | Material → element | `material.assign_material` |
| IfcRelVoidsElement | Opening cuts wall | `feature.add_feature` |
| IfcRelFillsElement | Door/window fills opening | `feature.add_filling` |

**Element lifecycle**: create_entity → placement → representation → container → (feature/type/material/pset incremental attachments).

## Typical Patterns

### Pattern 1: Skeleton (must build first)

```python
model = ifcopenshell.api.run("project.create_file")
project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
ifcopenshell.api.run("unit.assign_unit", model)
body = ifcopenshell.api.run("context.add_context", model,
    context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model3d)
site = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcSite")
building = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuilding")
storey = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingStorey")
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project, products=[site])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site, products=[building])
ifcopenshell.api.run("aggregate.assign_object", model, relating_object=building, products=[storey])
```

### Pattern 2: Wall (element + geometry + container)

```python
wall = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcWall")
ifcopenshell.api.run("geometry.edit_object_placement", model, product=wall)
rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
    context=body, length=5, height=3, thickness=0.2)
ifcopenshell.api.run("geometry.assign_representation", model, product=wall, representation=rep)
ifcopenshell.api.run("spatial.assign_container", model, relating_structure=storey, products=[wall])
```

### Pattern 3: Opening + Door (cut + fill)

```python
opening = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcOpeningElement")
rep = ifcopenshell.api.run("geometry.add_wall_representation", model,
    context=body, length=1.0, height=2.1, thickness=0.3)
ifcopenshell.api.run("geometry.assign_representation", model, product=opening, representation=rep)
ifcopenshell.api.run("geometry.edit_object_placement", model, product=opening, matrix=world_matrix, is_si=True)
ifcopenshell.api.run("feature.add_feature", model, feature=opening, element=wall)

door = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcDoor")
ifcopenshell.api.run("feature.add_filling", model, opening=opening, element=door)
```

### Pattern 4: Property Set (data attachment)

```python
pset = ifcopenshell.api.run("pset.add_pset", model, product=wall, name="Pset_WallCommon")
ifcopenshell.api.run("pset.edit_pset", model, pset=pset,
    properties={"FireRating": "REI90", "IsExternal": True})
```

## Recommended Reading Order

```
SKILL.md                    ← Behavioral constitution (MUST rules + 先 design JSON)
MODELING_WORKFLOWS.md       ← Pipeline strategy + Design JSON 框定 + discipline
DESIGN_JSON_SCHEMA.md       ← Design JSON 格式契约(LLM 框定意图)
DESIGN_PATTERNS.md          ← 概念设计 + 构件建造总索引
docs/design/README.md       ← 构件建造配方(roof/stairs/windows/parapet/balcony)
docs/api/README.md          ← API usecase 索引(14 categories)
docs/entities/README.md     ← 实体属性规格索引(REQ/OPT/enum)
docs/psets/README.md        ← 属性集索引(Pset/Qto 适用+属性)
docs/flows/README.md        ← 流程 + bug + 工具索引(design_builder/构建脚本/pitfalls)
```

## High-Frequency Usecase Quick Reference

| Scenario | Usecase |
|---|---|
| Create file | `project.create_file` |
| Create wall/door/window/slab | `root.create_entity(ifc_class="IfcWall"/"IfcDoor"/"IfcWindow"/"IfcSlab")` |
| Spatial tree aggregation | `aggregate.assign_object` |
| Element into storey | `spatial.assign_container` |
| Placement | `geometry.edit_object_placement(matrix=..., is_si=True)` |
| Wall geometry | `geometry.add_wall_representation` or `create_2pt_wall` |
| Slab geometry | `geometry.add_profile_representation` + `profile.add_arbitrary_profile` |
| Cut opening | `feature.add_feature(opening, wall)` |
| Fill opening | `feature.add_filling(door, opening)` |
| Assign type | `type.assign_type([elements], wall_type)` |
| Assign material | `material.assign_material(products, material_set)` |
| Attach pset | `pset.add_pset(product, name)` + `edit_pset(properties)` |
| Validate | `ifcopenshell.validate(json_logger)` |
