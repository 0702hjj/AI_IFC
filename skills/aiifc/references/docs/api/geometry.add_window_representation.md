# geometry.add_window_representation

## API Definition

```python
def add_window_representation(model, context: entity_instance, overall_height: Optional[float], overall_width: Optional[float], partition_type: Literal['SINGLE_PANEL', 'DOUBLE_PANEL_HORIZONTAL', 'DOUBLE_PANEL_VERTICAL', 'TRIPLE_PANEL_BOTTOM', 'TRIPLE_PANEL_HORIZONTAL', 'TRIPLE_PANEL_LEFT', 'TRIPLE_PANEL_RIGHT', 'TRIPLE_PANEL_TOP', 'TRIPLE_PANEL_VERTICAL'] = SINGLE_PANEL, lining_properties: WindowLiningProperties | dict[str, Any] | None, panel_properties: Optional[list[WindowPanelProperties | dict[str, Any]]], part_of_product: Optional[entity_instance], unit_scale: Optional[float]) -> entity_instance
```

*Source: api/geometry/add_window_representation*

## Import Surface

- run: `ifcopenshell.api.run("geometry.add_window_representation", model, ...)`

## Description

窗 Body 表示(窗套+窗扇+玻璃,SweptSolid)。尺寸用**项目单位**(mm 项目传 1500 不是 1.5)。
局部约定(实测 0.8.5 默认):X=宽 0→width;**Y=厚 50→125mm(中心 87.5mm)**;Z=高 0→height。

## Parameters

- **context** : Body 子上下文
- **overall_height / overall_width** : 窗总高/宽,项目单位(默认 0.9m/0.6m)
- **partition_type** : 默认 `SINGLE_PANEL`;多扇见文末 Known Issue
- **lining_properties / panel_properties** : `None` = 默认
- **unit_scale** : 省略自动算

## 开窗操作步骤(穿透/嵌入纪律)

```
洞口(≥1.5×墙厚,居中穿透) → add_feature → 窗体(嵌墙厚内) → add_filling → assign_container
```

1. 墙 placement 先居中于轴线(墙轮廓 Y∈[0,墙厚],偏移 `-墙厚/2`)
2. 洞口盒:厚度 ≥1.5×墙厚,法向偏移 `-洞口厚/2` → 跨墙中心线全穿透
3. 洞口/窗 placement 一律**世界坐标**,在 `add_feature` 前设好;禁止手算墙局部坐标
4. `add_filling` **不改窗位置**;窗矩阵 ≠ 洞口矩阵:窗偏移 = `-窗体厚度中心`
   (本 usecase 体 -87.5mm,薄玻璃盒 -25mm;纵墙 Rz(π/2) 时取正号)
5. 错位后果:玻璃贴房间内侧/悬出墙外 → design_review GI-07 报错

## 示意代码(南墙,墙厚 200,墙已居中 y=0)

```python
import numpy as np
import ifcopenshell.api
api = ifcopenshell.api.run

OT, BODY_C = 0.3, 0.0875   # 洞口厚(≥1.5×0.2) / 窗体厚度中心(米)
WIN_W, WIN_H, SILL = 1.8, 1.5, 0.9
mat = lambda x, y, z: np.array([[1,0,0,x],[0,1,0,y],[0,0,1,z],[0,0,0,1.0]])

# 洞口: 跨墙中心线 [-150,+150] 全穿透
opening = api("root.create_entity", model, ifc_class="IfcOpeningElement")
orep = api("geometry.add_wall_representation", model,
           context=body, length=WIN_W, height=WIN_H, thickness=OT)
api("geometry.assign_representation", model, product=opening, representation=orep)
api("geometry.edit_object_placement", model, product=opening,
    matrix=mat(2.0, -OT / 2, SILL), is_si=True)
api("feature.add_feature", model, feature=opening, element=wall)

# 窗: 偏移 -87.5 → 玻璃嵌在墙厚内(≠ 洞口矩阵)
window = api("root.create_entity", model, ifc_class="IfcWindow",
             name="Win-S1", predefined_type="WINDOW")
window.OverallHeight = WIN_H * 1000   # 项目单位 mm
window.OverallWidth = WIN_W * 1000
wrep = api("geometry.add_window_representation", model, context=body,
           overall_height=int(WIN_H * 1000), overall_width=int(WIN_W * 1000),
           lining_properties=None, panel_properties=None)
api("geometry.assign_representation", model, product=window, representation=wrep)
api("geometry.edit_object_placement", model, product=window,
    matrix=mat(2.0, -BODY_C, SILL), is_si=True)

api("feature.add_filling", model, opening=opening, element=window)
api("spatial.assign_container", model, relating_structure=storey, products=[window])
```

验证: GI-07 — 窗放置原点到墙中心线距离 ≤ 墙厚/2 + 25mm。

## Known Issue: multi-panel 必须显式 panel_properties (0.8.5)

`partition_type` 为 DOUBLE_*/TRIPLE_* 时默认只生成 1 个 panel 配置,取第 2/3 个会 `IndexError`。
绕过:每 panel 传一个空 dict:

```python
from ifcopenshell.api.geometry.add_window_representation import DEFAULT_PANEL_SCHEMAS
n = max(p for row in DEFAULT_PANEL_SCHEMAS[partition_type] for p in row) + 1
api("geometry.add_window_representation", model, context=body,
    overall_height=1500, overall_width=1500,   # 项目单位 mm
    partition_type="DOUBLE_PANEL_VERTICAL", panel_properties=[{}] * n)
```
