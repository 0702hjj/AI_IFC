# Pset — Common & Usage Rules(通用与使用规则)

## Common Psets(适用于所有 IfcElement 子类)

| Pset | Purpose |
|---|---|
| Pset_Condition | Element condition (new/existing/damaged) |
| Pset_ManufacturerOccurrence | Manufacturer info for single occurrence |
| Pset_ManufacturerTypeInformation | Manufacturer type info |
| Pset_ServiceLife | Service life |
| Pset_Warranty | Warranty info |
| Pset_EnvironmentalImpactIndicators | Environmental impact indicators |
| Pset_EnvironmentalImpactValues | Environmental impact values |

## Usage Rules

1. **挂 pset 前**, 用 `PsetQto.get_applicable_names(class)` 验证适用性(防乱挂)。
2. **填属性前**, 用 `doc.get_property_set_doc(pset)` 验证属性名与 schema 完全一致(防拼错)。
3. **真实文件只用子集** — 不是 Pset_WallCommon 所有属性都必填。
4. **Pset vs Qto**: Pset 是设计师指定(FireRating/IsExternal); Qto 是几何派生(NetVolume/Length), 几何变需重算。

## Tagging Experience(打标经验)

5. **每个产品类都要 pset + material, 一个都不能漏。** viewer 属性面板空 = 没挂 pset。挂 pset 的循环要遍历**所有**产品类(`model.by_type()`), 新增元素类型时扩展循环。
6. **写新元素类型代码前, 先查适用 pset**:
   ```python
   from ifcopenshell.util.pset import PsetQto
   q = PsetQto("IFC4")
   [n for n in q.get_applicable_names("IfcRoof", pset_only=True) if "Common" in n]
   # → ['Pset_RoofCommon']
   ```
7. **材质同纪律**: 每个产品类至少 `material.assign_material` 一次(roof→tiles, chimney→brick, stair/columns→concrete, railing→steel), 否则 viewer 默认灰。
8. **验证**: 导出后 `util.element.get_psets(e)` + `get_material(e)` 抽查每个产品类, 空列表=漏了。
