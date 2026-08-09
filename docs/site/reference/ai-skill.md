# AI Skill（aiifc）

面向 AI agent 的 **IfcOpenShell 建模 skill**——让 AI 直接写 `ifcopenshell.api` 代码来创建 / 修改 IFC 模型。与 [AI 接入](/reference/ai) 的 REST 方式互补：REST 适合「改属性」这类细粒度编辑，skill 适合「从零建模型 / 大改几何」这类整体生成。

## 它是什么

`skills/aiifc/` 是一个遵循 [Anthropic Agent Skills 规范](https://github.com/anthropics/anthropic-sdk-python) 的薄参考 skill：

- **SKILL.md**：行为宪法（MUST 1-29）——骨架先行、容器必填、世界坐标、开洞纪律、三层校验、脚本契约（PARAMS + 确定性 GlobalId + build 入口），design JSON 仅作复杂几何的起草草稿。
- **references/**：103 个 API 分页、8 个组件 recipe（楼梯/屋顶/窗/女儿墙/阳台）、13 个可运行 flows、6 份方法论参考（SKD_OVERVIEW / MODELING_WORKFLOWS / DESIGN_JSON_SCHEMA / SPATIAL_QUALITY 等）。
- **templates/**：可复制的完整示例脚本（如 `build_skeleton.py` 最小模型）。
- **requirements.txt**：运行 flows 需要的 Python 依赖（`ifcopenshell` / `ifcquery` / `numpy`，PyPI 官方发布，无本地源码依赖）。

skill 结构源自仓库历史中的 SimpleCADAPI skill 设计解剖（`research/ifc/simplecadapi_skill_anatomy.md`），并按 IFC 领域重写：**按动作拆模块、四层渐进展开、每层单一职责、MUST 条款串联**。

## 用 skill 建模型（AI 视角）

agent 加载 skill 后，按 Pipeline 顺序用 `ifcopenshell.api.run(...)` 写代码：

```
Skeleton（Project→Site→Building→Storey）
  → Elements（墙/板/梁柱，entity + placement + representation + container）
  → Openings（洞口 + 门窗填充）
  → Data（类型 / 材质 / 属性集）
  → Export（model.write + ifcopenshell.validate）
```

复杂户型 / 异形 / 多楼层先输出 **design JSON**（几何意图，不写坐标），经 `design_builder.py` 规范化后再生成构建脚本——避免坐标漂移。

## 安装到你的 agent

skill 是 agent 无关的目录包，任何支持 Agent Skills 规范的 agent（opencode、Claude Code、Cursor 等）都能加载：

```bash
# 1) 从仓库复制或解压分发包
cp -r skills/aiifc ~/.config/opencode/skills/aiifc
# 或用打包器生成 tar.gz 分发包
python tools/skill_pack_aiifc.py --archive   # 产出 skills/dist/aiifc.tar.gz
tar xzf skills/dist/aiifc.tar.gz -C ~/.config/opencode/skills/

# 2) 安装运行依赖（flows 用）
uv pip install -r skills/aiifc/requirements.txt
```

## 与平台 REST API 的关系

| 方式 | 场景 | 入口 |
|---|---|---|
| **REST 编辑 API** | 在既有脚本上定向修改（PARAMS 暂存 / edit-call 标量改写）、版本与 diff | `:8100/models/{id}/...`（见 [AI 接入](/reference/ai)） |
| **aiifc skill** | 从零建模型、大改几何、复现上传 IFC（bootstrap），产出契约化构建脚本 | agent 直接写 Python（`ifcopenshell.api`） |

两者互补：skill 负责「生成 / 大改」，平台的沙箱执行 / 版本 / XKT 重转链路负责「落盘与追踪」。

## 分发与打包

- 打包器：`tools/skill_pack_aiifc.py`（校验 SKILL.md frontmatter / 必需路径 / 无噪声，复制到 `skills/dist/`，可选打 tar.gz）。
- 产物 agent 无关：`SKILL.md` + `references/` 即 Anthropic Agent Skills 规范。
- CI（`skill (aiifc pack + flows smoke)` job）会在每个 PR 校验打包产物完整性并跑 flows 冒烟。

## 许可

`skills/aiifc/` 声明为 **LGPL-3.0**（`SKILL.md` frontmatter `license` 字段）。文档参考自 [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) 官方文档（LGPL-3.0）。
