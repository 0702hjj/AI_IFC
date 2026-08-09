# 版本与 Diff Viewer

## 版本快照

script-backed 模型的**大版本** = 一次显式「保存版本」：

- 脚本与定位 map **全量保留**：`{dataDir}/models/{id}/scripts/v{n}.py` + `v{n}.map.json`（+ `v{n}.meta.json` 备注），编号 lockstep（`n = max(脚本侧, IFC 侧) + 1`），只增不改、原子写。
- IFC **只物化最新**：`versions/v{n}.ifc` 仅保留最新大版本；历史版本是有脚本可重建的缓存——diff/下载历史版本时从对应脚本沙箱重跑生成（结果缓存于 `ifc_cache/`，LRU 容量 4 淘汰）。重建产物与原快照**仅语义相等**（确定性 GlobalId 保证对齐，IFC 头时间戳使字节不同），因此版本间比较一律走语义 diff，不做字节断言。
- 存量（迁移期）无脚本的实体编辑快照保留不清理。
- 暂存链步（小版本）不产生版本快照，只在步间做轻量脚本 diff；超 10 步环窗丢最老，save 压实为大版本并清空缓冲。

plain 模型（外部上传、无脚本）没有大版本链，仅当前态可查看/对比。

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
- 历史版本 IFC 不在盘上时，diff 触发按需重建（见上）；大版本间另有脚本 diff（text + PARAMS 键级），见 [Script 编辑与版本对比](/reference/design-edit)。

接口契约见 [IFC 编辑 API](/reference/edit-api)。
