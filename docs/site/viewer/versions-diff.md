# 版本与 Diff Viewer

## 版本快照

每次 commit 生成一个不可变版本快照，只增不改、原子写：

- 首次 commit：先把原始上传文件快照为 `v1`，落盘后再快照新文件为 `v2`。
- 之后每次 commit 成功产生 `v{n+1}`。
- 快照存放于 `{dataDir}/models/{id}/versions/v{n}.ifc`。

## Diff 面板

工具栏「Diff」打开对比面板：

1. 选择 base（v1 / v2 / …）与 target（版本或 `current`）。
2. 点击「对比」：**绿 = 新增、黄 = 修改、红 = 删除**。
3. 点击条目定位构件；修改条目可展开查看字段级 old → new。
4. 「清除」复位着色。

## Diff 语义

- 以 **GlobalId** 为实体标识：`added` / `removed` 为 guid 列表；`changed` 为实体直接属性与 pset 属性的字段级 old → new。
- 基于 ifcdiff，仅以 `attributes` / `property` 两种 relationship 运行；entity 引用属性（ObjectPlacement、Representation 等几何表示层）不参与比较，**当前不提供几何 diff**。
- 删除构件在当前 XKT 中已无几何，只进入红色列表（设计决策）。
- base/target 均为不可变版本时，结果缓存在 `versions/diff-{base}-{target}.json`；`target="current"` 不缓存。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
