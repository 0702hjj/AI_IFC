# AI_IFC 迭代计划 v2：辅助设计师的 plan → DXF → IFC 工作流 + 轻量差异引擎

**日期：** 2026-08-05
**状态：** 设计草案
**定位：** 辅助设计师开发。AI 首次生成结束自动存一版；用户在其上修改、确认后再存下一版。不做逐步回溯链。

---

## 0. 三条主线结论（2026-08-05 讨论确认）

| 主题 | 结论 |
|---|---|
| **工作流** | 固定 plan → DXF → IFC 三阶段（superpowers 式 skill 规定顺序，可依用户输入跳步） |
| **用户修改** | 改 design JSON（语义参数层），前端表单 → 更新 design JSON → 重生成 |
| **diff 引擎** | 只做大版本间差异（轻量）；不做逐步回溯链，用**暂存区**（WPS 式 <- -> 前后切换，默认保留 10 次修改） |

---

## 1. 版本与暂存模型（WPS 式，核心约束）

**需求**：不要逐步回溯链路；只要「大版本之间」的差异，且轻量（不是 git 的 commit 链，是 git 的 tag 对比）。

**机制（暂存区 + 大版本）**：

```
[编辑暂存区]   ← 设计师/AI 在 design JSON 上的修改（最多保留 10 步）
    │  <- -> 可前后切换（WPS 式撤销/重做），仅内存态，不落盘
    │
    ├─ 未确认 → 超 10 步自动丢弃最旧；刷新/放弃即丢（不产生任何版本/diff）
    │
    └─ 确认保存（Save）→ 丢弃暂存链 → 生成大版本 v{n}
            ├─ designs/v{n}.json   （design JSON 快照）
            ├─ versions/v{n}.ifc   （派生 IFC 快照，供渲染/回退）
            └─ 计算 v{n-1} ↔ v{n} 的差异并保存（diff 结果）
```

- **大版本 = 用户主动保存的点**（AI 首次生成结束自动存一版，之后用户确认保存再存）。
- **暂存区不落盘、不入版本**；只在保存的瞬间转化为「两个大版本之间的 diff」。
- **回退** = 取某个 `designs/v{n}.json` 恢复 → 重生成 IFC，而不是复制 IFC。

---

## 2. 工作流：plan → DXF → IFC（skill 层）

### 2.1 定位与可行性

- **可行性高**。design JSON 天然是 plan 层（纯意图、无坐标）；DXF 是 2D 中间件；IFC 是最终产物。`research/ifc/README.md` 已有 cad-to-shapely → IfcOpenShell 选型底稿。
- 本仓库 `IfcOpenShell/src/ifcmcp` + `ifcquery` 提供现成读取能力（见 §3），其中 `ifc_plot` 可出 2D 图纸——**2D 预览不依赖 DXF**，DXF 作为可交付文件格式。

### 2.2 实现方式：aiifc 新增「工作流 skill」（superpowers 式）

在 `skills/aiifc/` 下新增一个 workflow skill，规定三阶段顺序：

```
① plan   → design.json（AI 输出设计意图）
② dxf    → plan.dxf（由 design.json 生成 2D 平面图，ezdxf）
③ ifc    → model.ifc（由 design.json + design_builder + build_script 生成）
```

- **顺序固定**，但 agent 可依用户输入跳步（如用户直接说「改这面墙」→ 只走 ③；说「先看看平面」→ 只走 ①②）。
- 每阶段产物落盘：`designs/v{n}.json` / `plan.dxf` / `versions/v{n}.ifc`。
- 前端可用 svg 渲染 DXF 做 2D 预览，作为「让用户确认 plan」的可视化手段。

---

## 3. 用户修改：design JSON 编辑 + 确定性构件身份

### 3.1 编辑对象

**design JSON 是唯一编辑面**（不是 py 脚本，不是 IFC 几何）。前端参数表单 → 更新 design JSON → 重生成 IFC。

### 3.2 确定性构件身份（diff 可对齐的地基）

`build_script_template.py` 目前**不设置 GlobalId**（ifcopenshell 每次随机生成）——这是跨版本 diff 无法对齐的根因。

**方案（采纳建议 + 关键补充）**：

1. **design JSON Schema 增加稳定 `key`**：
   - 每条 wall / opening / slab / stair 携带 `key`（如 `"1F:wall:2"`、`"1F:opening:0"`）。
   - `design_builder` 保留已有 key；新元素分配确定性 key（`{storey}:{kind}:{n}`）。
   - 前端编辑时 key 保持不变（插入新元素才生成新 key）→ 跨版本稳定。

2. **build_script_template 写入确定性 GlobalId**：
   ```python
   key = f"{storey}:wall:{gi}:s{si}"
   guid = str(uuid5(NAMESPACE_AI_IFC, key))   # 确定性
   wall = api("root.create_entity", model, ifc_class="IfcWall", GlobalId=guid, ...)
   ```

3. **写回映射 Pset**：每构件挂 `Pset_AIIFC`，含 `designKey`（= key）与 `designId`（= GlobalId 前 8 位），实现 **IFC 构件 ↔ design JSON 条目 双向映射**。

---

## 4. 差异引擎：两个大版本之间（轻量）

### 4.1 需求（用户反馈）

- 现在 ifcdiff 字段级 old→new 太细太重（审计日志式）。
- 要的是：**两个大版本之间「哪些被改了」**，且能标识「用户可能不希望保留的改动」。

### 4.2 双路径 diff（复用 ifcquery.info 结论）

**路径 A：design JSON 语义 diff（主，覆盖有 provenance 的模型）**
- 对比 `designs/v{n-1}.json` ↔ `designs/v{n}.json`，按 `key` 对齐。
- 输出**语义**：墙轴从 A 移到 B、窗宽 1.5→1.8、板增减……非 IFC 字段 old→new。

**路径 B：IFC 语义指纹 diff（兜底，覆盖外部上传/无 design JSON 模型）**
- 复用本仓库 `ifcquery.info()` 的 `geometry_summary` + psets 指纹（轮廓点/拉伸深度/placement 矩阵，**不是原始 STEP**）。
- 对两个 IFC 各跑一次指纹提取，按 GlobalId 对齐比较 → 构件级摘要 diff。
- 无需自研解析；`ifcquery` 已在 skill requirements（本轮评估是否纳入 edit-service 依赖）。

**统一输出 schema（两条路径一致，UI 无感知）**：

```json
{
  "base": "v1", "target": "v3",
  "changed": [
    {
      "key": "1F:wall:2",
      "designId": "abcd1234",
      "type": "IfcWall",
      "human_label": "1F 南外墙",
      "changes": [
        {"field": "axis.end", "old": [12,0], "new": [14,0], "unit": "m"},
        {"field": "thickness", "old": 0.2, "new": 0.3}
      ]
    },
    {"key": "1F:opening:0", "type": "window", "action": "added"},
    {"key": "2F:wall:3", "type": "IfcWall", "action": "removed"}
  ]
}
```

### 4.3 与暂存模型融合

- diff **只在保存时计算**（`v{n-1} ↔ v{n}`），一次一个结果，独立无状态。
- 暂存区内部的变化**不产生任何 diff**（丢弃即无痕）。
- 「用户可能不希望保留」信号：AI 生成完成的自动版本，其 IFC 挂 `Pset_AIIFC.AISummary`；diff 结果可过滤「AI 生成 vs 用户确认」来源。

### 4.4 现有 ifcdiff 字段级 diff 的去留

- **保留为兜底路径的内部实现**（路径 B 之外），但**不再作为用户可见的默认 diff**。
- 用户可见 diff 统一走 §4.2 语义 schema。

---

## 5. 前端与交互

- **diff 呈现**：版本选择（两个大版本）→ 构件级列表（默认折叠）+ 字段级明细（展开）。对应现有 Diff Viewer 改造。
- **暂存区 UI**：编辑面板带 `<-` `->` 撤销/重做（10 步）+「保存版本」按钮 +「放弃」。
- **2D 预览**：DXF → svg 渲染，plan 确认用。

---

## 6. 实施顺序（沿用 skill → API → CI → 文档，每步一次 commit）

| 序 | 迭代 | 内容 | 涉及 |
|---|---|---|---|
| 1 | **workflow skill** | plan→DXF→IFC 三阶段 skill + DXF 生成 | `skills/aiifc/` |
| 2 | **确定性身份** | DESIGN_JSON_SCHEMA 加 `key`；build_script 写确定性 GlobalId + designKey Pset | `skills/aiifc/references/DESIGN_JSON_SCHEMA.md`、`flows/build_script_template.py` |
| 3 | **版本/暂存模型** | 保存→大版本（designs/v{n}.json + versions/v{n}.ifc）；回退=恢复 design JSON；暂存区（10 步） | `viewer/server`、`viewer/edit-service`、`viewer/web` |
| 4 | **差异引擎** | design JSON 语义 diff（主）+ IFC 指纹 diff（兜底，ifcquery.info）；统一 schema；Diff Viewer 改造 | `viewer/edit-service/app/diffing.py`、`viewer/web` |
| 5 | **前端参数编辑** | 构件选中→design JSON 参数表单→更新→重生成 | `viewer/web`、`viewer/server` |
| 6 | **CI/测试** | 各迭代测试 + 新 diff 引擎单测 | `tests/`、CI |
| 7 | **文档** | 文档站/README 更新（版本模型、diff、工作流） | `docs/` |

> 注：§4.2 路径 B 依赖 ifcquery 是否纳入 edit-service 依赖——若纳入，`viewer/edit-service/pyproject.toml` 加 `ifcquery`。

## 7. 与后续展望的关系

- **前端参数编辑**（本迭代 5）= 之前确认的「改 design JSON 语义参数层」。
- **Revit 在线（自由几何编辑）**仍属远期独立项目，不在本迭代。
