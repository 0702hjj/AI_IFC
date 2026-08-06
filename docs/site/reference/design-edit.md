# Design JSON 编辑与版本对比（辅助设计师）

面向「辅助设计师」的编辑与版本模型：**design JSON 是单一真相源**，IFC 是派生产物。用户/AI 的修改落在 design JSON（语义参数层），不做逐步回溯链，只在**大版本之间**做轻量语义对比。

## 三个核心概念

### 1. Design JSON（编辑面）

`design JSON` 描述设计意图（墙轴 / 洞口沿轴位置 / 厚度 / 层高），不含坐标计算。前端选中构件（通过 `Pset_AIIFC.designKey` 定位到 design JSON 条目）→ 改参数 → 重生成 IFC。

每个构件携带稳定 `key`（如 `"1F:wall:0"`）：

- 编辑时 key 不变 → 跨版本 diff 可对齐。
- 生成时由 `uuid5(NAMESPACE, key)` 派生**确定性 GlobalId**（同一 key 多次运行 GlobalId 不变），并写入 `Pset_AIIFC.designKey`。

### 2. 暂存区（WPS 式，最多 10 步）

编辑先进入内存暂存（最多保留 10 个状态），支持 `<-` / `->` 前后切换：

- **未确认保存** → 放弃即丢弃，**零 diff、零版本**。
- **确认保存** → 丢弃暂存链，生成**大版本**。

```
编辑暂存（10 步，仅内存，可 undo/redo）
   ├─ 放弃 → 丢弃（无痕）
   └─ 保存 → 大版本 v{n}（designs/v{n}.json + versions/v{n}.ifc）
             └─ 只算 v{n-1} ↔ v{n} 的一次 diff
```

### 3. 大版本与差异

- **大版本** = 用户/AI 主动保存的点（AI 首次生成结束自动一版；之后设计师确认保存）。
- 成对快照：`models/{id}/designs/v{n}.json` + `models/{id}/versions/v{n}.ifc`。
- **回退** = 恢复某版 design JSON → 重生成 IFC（不复制 IFC、不逐步回退）。
- **差异**只在两个大版本之间计算，轻量、独立、无状态。

## 差异引擎（两个大版本之间）

主路径 **design JSON 语义 diff**（覆盖有 provenance 的模型，下例为响应 envelope `{code,message,data}` 的 `data` 字段内容）：

```json
{
  "base": "v1", "target": "v2", "engine": "design-json",
  "changed": [
    {"key": "1F:wall:0", "type": "IfcWall", "human_label": "1F 墙 1 段 @ [0,0]→[14,0]",
     "changes": [{"field": "t", "old": 0.2, "new": 0.3}, {"field": "axis[1]", "old": [12,0], "new": [14,0]}]},
    {"key": "1F:wall:1", "type": "IfcWall", "human_label": "1F 墙 1 段 @ [0,8]→[12,8]", "action": "removed"},
    {"key": "1F:opening:1", "type": "IfcDoor", "human_label": "1F 门 w=1.0m", "action": "added"}
  ]
}
```

兜底路径 **IFC 语义指纹 diff**（覆盖外部上传 / 无 design JSON 模型）：比较构件指纹（type / name / psets，按 designKey 或 GlobalId 对齐），不解析原始 STEP。

## API

全部经 Go server（`/api/v1`）代理：

| 端点 | 语义 |
|---|---|
| `GET /api/v1/models/{id}/design` | 当前 design JSON（暂存态或最近保存） |
| `PUT /api/v1/models/{id}/design` | 暂存一次 design JSON 编辑 |
| `POST /api/v1/models/{id}/design/undo|redo|discard` | 暂存导航 / 放弃 |
| `POST /api/v1/models/{id}/design/regenerate` | 由暂存 design JSON 重生成 IFC（design_builder → build_script） |
| `POST /api/v1/models/{id}/design/save` | 暂存晋升为大版本（成对快照） |
| `GET /api/v1/models/{id}/designs` | 大版本列表 |
| `POST /api/v1/models/{id}/design/rollback` | 恢复某版 design JSON |
| `POST /api/v1/models/{id}/design/diff` | design JSON 语义 diff（主） |
| `POST /api/v1/models/{id}/design/diff-ifc` | IFC 指纹 diff（兜底） |

前端：查看器选中构件 → Design 面板参数表单 → 暂存修改 / 撤销 / 重做 / 放弃 → 重生成 + 保存大版本；版本对比面板选择两个大版本看语义差异。

## 与旧 IFC 编辑的关系

- design JSON 生成的模型：编辑/版本/差异走本页模型。
- 外部上传的 IFC（无 design JSON）：差异退化为 IFC 指纹 diff；属性级 override 仍可用（见 [IFC 属性编辑](/viewer/editing)）。
