"""
flows/style_color.py — 染色:双层染色法(材质语义层 + 构件直染层)。

建模管线 Data 阶段的固定一步。两层缺一不可:

    ① 语义层(材质样式): style → IfcMaterial
       新增构件绑同材质即继承颜色;BIM 语义正确
    ② 直染层(表示样式): style → 每个构件的 Body IfcShapeRepresentation
       **必须做**:几何引擎对多层 IfcMaterialLayerSet(如 Brick+Plaster)
       解析不出材质样式(实测回退默认灰),直染是 Revit 同款做法,viewer 最稳

样式类用 IfcSurfaceStyleRendering(不是 Shading):
    Rendering 是 Shading 的子类且是 web 查看器(web-ifc / That Open)的主读路径;
    必须带 ReflectanceMethod(用 "NOTDEFINED" = 物理光照模型)。
    注意:一个 IfcSurfaceStyle 只能装一个 Rendering/Shading 项(add_surface_style
    会去重),不要给同一 style 同时加两种。

验证方法(几何迭代器 = viewer 同款解析):
    import ifcopenshell.geom
    it = ifcopenshell.geom.iterator(ifcopenshell.geom.settings(), model, 1)
    it.initialize()
    while True:
        e = it.get()
        print(e.name, [(m.name, m.diffuse.components, m.transparency)
                       for m in e.geometry.materials])
        if not it.next(): break
"""

import ifcopenshell
import ifcopenshell.api

api = ifcopenshell.api.run


def make_style(model, name, rgb, transparency=0.0):
    """创建 IfcSurfaceStyle(Rendering 项)。rgb ∈ [0,1];Transparency 0=不透明,玻璃 0.7。"""
    style = api("style.add_style", model, name=name)
    api("style.add_surface_style", model, style=style,
        ifc_class="IfcSurfaceStyleRendering",
        attributes={
            "SurfaceColour": {"Name": None, "Red": rgb[0], "Green": rgb[1], "Blue": rgb[2]},
            "Transparency": transparency,
            "ReflectanceMethod": "NOTDEFINED",
        })
    return style


def add_color(model, context, material, name, rgb, transparency=0.0):
    """① 语义层:样式挂材质。返回 IfcSurfaceStyle(供 colorize 复用)。"""
    style = make_style(model, name, rgb, transparency)
    api("style.assign_material_style", model,
        material=material, style=style, context=context)
    return style


def colorize(model, products, style):
    """② 直染层:样式直接挂到每个构件的 Body 表示(多层材质构件必须)。"""
    for p in products:
        if not p.Representation:
            continue
        for rep in p.Representation.Representations:
            if rep.RepresentationIdentifier == "Body":
                api("style.assign_representation_styles", model,
                    shape_representation=rep, styles=[style])


# 常用建筑色板
PALETTE = {
    "brick":    (0.65, 0.25, 0.15),   # 砖红
    "plaster":  (0.90, 0.87, 0.80),   # 米白
    "concrete": (0.60, 0.60, 0.60),   # 灰
    "roof_tile": (0.55, 0.22, 0.16),  # 红瓦
    "wood":     (0.45, 0.30, 0.15),   # 棕木
    "glass":    (0.60, 0.80, 0.90),   # 浅蓝玻璃(配 transparency=0.7)
    "steel":    (0.55, 0.57, 0.60),   # 钢
}


# Usage(rural_villa 同款):
#   st = add_color(model, body, brick, "Brick-Red", PALETTE["brick"])
#   colorize(model, ext_walls + gables, st)          # 多层材质墙必须直染
#   st_glass = add_color(model, body, glass, "Glass-Blue", PALETTE["glass"], 0.7)
#   colorize(model, windows, st_glass)
