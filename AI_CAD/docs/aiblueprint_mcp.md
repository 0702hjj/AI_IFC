# AIBlueprint MCP 使用手册

> 来源：`thebossnow/aiblueprint-mcp`(MIT）的 README（完整 API 参考）+ HANDOFF.md(Gotchas/设计决策）+ 本项目实测记录（2026-08-05,mall_l1 集成案例）。HANDOFF 提及的三份 Hermes 私有文档（aiblueprint-mcp-reference / offset-fillet-algorithms / autocad-mcp-evaluation）从未公开发布，本手册为其替代固化版本。

## 1. 定位：与 cadpy 的分工

| | aidxfv1 / cadpy | aiblueprint MCP |
|---|---|---|
| 形态 | CLI 批量生成管线 | MCP 会话式工具服务器（stdio) |
| 粒度 | 整脚本一次生成（`gen_dxf()`) | 逐实体操作 |
| 状态 | 无状态 + sourceHash 溯源 | 有状态会话 + 快照 undo/redo |
| 适合 | plan→cad 批量生成、落盘交付 | 交互微调、量测核查、人审改图、视觉自查 |

**分工原则**：批量生成走 cadpy；打开产物逐实体核查/修改走 MCP。

## 2. 接入方式

`AI_CAD/opencode.json`（已配置）:

```json
"mcp": {
  "aiblueprint": {
    "type": "local",
    "command": ["<repo>/resource/aiblueprint-mcp/.venv/bin/aiblueprint-mcp"],
    "enabled": true,
    "environment": {
      "AIBLUEPRINT_WORKSPACE": "<repo>/AI_CAD/results/mcp"
    }
  }
}
```

- 配置启动时加载，**改配置必须重启 opencode**
- **venv 不可搬迁**：移动项目目录后入口脚本 shebang 失效（报 ENOENT)，须 `rm -rf .venv && uv venv && uv pip install -e .` 重建
- 可选 `AIBLUEPRINT_LIBRECAD_BIN` 指向 librecad 二进制启用 `view.preview`(dxf2png)；不配则用 matplotlib 的 screenshot/export
- 打开外部 DXF 前须先拷入 AIBLUEPRINT_WORKSPACE（沙箱限制）

## 3. 工具参考（8 工具 / 40+ 操作）

| 工具 | 操作 |
|---|---|
| `drawing` | create / open / info / save / list / switch / undo / redo |
| `entity` | 建：create_line/circle/polyline/rectangle/arc/text/mtext/hatch、import_boundary（测量点或 GeoJSON 地块）；查：list/get/measure（面积/周长/长度）；改：copy/move/rotate/scale/mirror/offset/array/fillet/erase |
| `layer` | list / create / set_current / set_properties / freeze / thaw / lock / unlock |
| `block` | list / insert / insert_with_attributes / get_attributes / update_attribute / define |
| `annotation` | create_text / create_dimension_linear/aligned/angular/radius（支持 dim_overrides: dimtxt/dimasz/dimlunit/dimclrd/dimclre/dimclrt/dimtxsty)/ create_leader |
| `view` | screenshot(matplotlib,LLM 可见 PNG)/ preview(LibreCAD dxf2png)/ export(PNG/PDF/SVG/GeoJSON) |
| `project` | start / question / answer / profile / status / reset / counties / cities / generate_site_plan |
| `compliance` | 面积/退让/覆盖率/限高检查 + 带法条引用的完整报告（加州数据） |

## 4. 规范工作流程

```
A. 问卷驱动(独有链路):
project.start → question/answer 循环(条件分支: HOA=no 跳过追问)
  → profile(州→县→市→HOA 分层取最严, 每条带法条引用)
  → generate_site_plan(自动布局 + 合规校验 + 标题栏)

B. 手动建图:
drawing.create → layer.create → entity.create_* / block.insert
  → annotation.create_dimension_*
  → view.screenshot / preview (视觉自查)  ←──┐
  → entity.move/offset/fillet 修正 ─────────┘ 监察循环
  → drawing.save / view.export

C. 产物核查(与 cadpy 集成):
cp 外部 DXF 入 workspace → drawing.open → entity.list(按图层统计)
  → entity.measure(量测) → entity.move 微调 → view.screenshot 确认
  → undo 回滚或 drawing.save 落盘
```

## 5. Gotchas（踩坑记录）

1. **ezdxf 1.4+ 标注 API**：覆盖写 `dim.dimstyle.dxf.dimtxt = v`；不要 `dim.dxf.override()`，`add_aligned_dim()` 无 `override={}` kwarg
2. **offset 方向**：正值=外扩（CCW 走向）；顺时针矩形须用**负值**内缩
3. **fillet 方向向量**：两线共端点时，从交点向**远端点**取方向再取反（近端点可能零向量）
4. **实心填充**:`hatch.set_solid_fill()`，不要 `set_pattern_fill("SOLID")`
5. **dxf2png 路径**：传绝对路径 `-o` 会路径翻倍，用相对路径或临时目录
6. **工作区沙箱**:`config.resolve_path()` 拒绝对路径和 `..` 逃逸；测试用 monkeypatch `AIBLUEPRINT_WORKSPACE`
7. **undo 机制**：每次修改前整文档序列化做 checkpoint;`backend.batch()` 可把多操作并为一个 checkpoint

## 6. 实测记录（2026-08-05,mall_l1.dxf 集成案例）

测试方案 P0-P7 见会话记录；已完成项：

| 项 | 结果 |
|---|---|
| P7.1 打开 + 按图层统计 | 111 实体 / 7 图层，与 cadpy 读回 Counter 完全一致 |
| P7.2 量测中庭（A-VOID, handle 9D) | 面积 1,200,000,000 mm²(1200 m²)、周长 224,000 mm，与设计值精确一致 |
| 后端全流程（Python 直驱） | 16 问问卷→LA 法规解析（带引用）→generate_site_plan→DXF/PNG/PDF 落盘→move/undo 验证，全部通过 |

## 7. 已知缺口

- **无建筑语义工具**：只有实体级操作，没有墙/门/窗级命令（我们 v1.1 helpers 的职责）
- **法规数据仅加州**:`data/jurisdictions/ca/`(state + 10 县 + 15 市 JSON)；格式可扩展（国内规范可照 schema 换数据）
- **自动 site plan 仅支持矩形地块**；不规则地块可 import_boundary + compliance，但不能自动布 ADU(issue #22)
- **Live LibreCAD backend**(bivex TCP bridge，直连内存 Document）未实现，值得跟踪（issue #1)——若落地，人审环节"AI 改图→LibreCAD 实时可见"即通
