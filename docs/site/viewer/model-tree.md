# 模型树与属性检查

## 模型树

左侧面板展示按空间结构组织的模型树（Site → Building → Storey → 构件），基于 converter 导出的元数据构建：

- **搜索**：按名称或类型过滤。
- **类型过滤**：按 IFC 类型（如 IfcWall）过滤构件。
- **显隐**：逐节点切换可见性。
- **定位**：点击节点，相机飞行到构件并高亮选中。

## 属性检查器

右侧属性面板显示选中构件的属性集（pset）：

- pset 分组折叠，默认展开第一个。
- 属性搜索与复制（写入剪贴板）。
- 白名单字段（Name / Description / Classification / FireRating / Comments）可行内编辑，保存为 override 并带修改标记，见 [IFC 属性编辑](/viewer/editing)。

## 技术说明

元数据由 converter 以 xeokit 标准元模型 JSON 导出，`metaObjects[].id` 为 IFC GlobalId，与 XKT 实体 id 一致，因此选中、着色、diff 结果全部对齐。Schema 见 [Viewer REST API](/reference/rest-api) 的 metadata.json 一节。
