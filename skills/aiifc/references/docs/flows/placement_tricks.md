# Placement Tricks — 放置 / 开洞技巧(可累加)

> placement(放置)与 opening(开洞)的操作技巧。**可累加**: 新技巧补一节 `## 标题`。

---

## Multi-Axis Rotation Matrix(多轴旋转放置)

`geometry.edit_object_placement` 接受任意 4×4 矩阵。除标准 Z 旋转(朝向)外,可链 Y 旋转(前后倾,如遮阳百叶)或 X 旋转(纵向坡,如坡道):

```
M = T(x,y,z) @ Ry(tilt) @ Rz(phi)   # 先旋转(Rz 后 Ry), 最后平移 — 不要旋转目标位置
```

- 约定: 先旋转(Rz then Ry), 后平移 → 矩阵积 `T @ Ry @ Rz`
- `tilt > 0` 顶边外倾(正 Y 旋转)
- Rx(绕 X)可类似链接(坡道)
- 百叶倾斜板用 `fm @ T @ Rx` 矩阵链(见 windows_types / louver)

## Opening Placement(开洞定位)

- **开洞坐标用世界坐标**, 在 `feature.add_feature` 前设置(它自动减宿主墙原点, 转墙相对)。
- **不要手设墙局部坐标** — 会双 offset(见 pitfalls O2)。
- **开洞厚度 ≥ 1.5× 墙厚**, 确保穿透(见 pitfalls O1)。
- 沿墙轴定位: `opening_matrices(墙轴, along)` 展开成坐标(见 build_script_template)。

## Wall Placement(墙定位)

- **居中墙**: `wall_matrix(x1,y1,x2,y2,t,elev)` 把墙轴居中(偏移 -t/2), 消除偏侧缝隙。
- 多层建筑: 放置矩阵传**世界坐标 z**(storey elevation), usecase 内部补偿相对 storeys; 不要传 storeys 局部 z(会重叠)。

---

**累加规则**: 新技巧补一节 `## 标题`(矩阵公式 / 定位约定 / 来源)。
