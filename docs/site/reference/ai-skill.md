# AI Skill（aiifc / aiplan / aidxfv）

> 平台的 AI 生成能力以 **skill 包**交付，分两条线：**IFC 侧**（`aiifc`）与 **plan→cad 侧**（`aiplan` + `aidxfv` v3）。skill 面向 AI agent——agent 加载后直接写代码 / 跑命令来生成或修改模型，与 [AI 接入](/reference/ai) 的 REST 方式互补：REST 适合「改属性」这类细粒度编辑，skill 适合「从零建模型 / 整体生成」这类大动作。

## 管线总览

plan→cad 侧是 AI BIM 管线的入口与中段：`aiplan` 把外部资料归一成任务书，`aidxfv` v3 把任务书落地成图纸，下游 bim 消费：

```
外部资料 ──► aiplan ──┬─► plan.json（任务书）──────────► aidxfv v3 ──► building.json + 各层 DXF ──► bim
                      └─► bim_supplement.json（BIM 补充）─────────────────────────────────────► bim
```

| skill | 阶段 | 输入 | 输出 |
|---|---|---|---|
| `aiplan` | plan（管线入口） | 无特殊要求——外部资料（图片/PPT/技术文档/用户对话） | `plan.json` + `bim_supplement.json` |
| `aidxfv3` | cad（管线中段） | `plan.json`（只读）+ 用户额外描述 | `building.json` + 各层 DXF |

## aiifc（IFC 生成/修改）

面向 AI agent 的 **IfcOpenShell 建模 skill**——让 AI 直接写 `ifcopenshell.api` 代码来创建 / 修改 IFC 模型。

### 它是什么

`skills/aiifc/` 是一个遵循 [Anthropic Agent Skills 规范](https://github.com/anthropics/anthropic-sdk-python) 的薄参考 skill：

- **SKILL.md**：行为宪法（MUST 1-29）——骨架先行、容器必填、世界坐标、开洞纪律、三层校验、脚本契约（PARAMS + 确定性 GlobalId + build 入口），design JSON 仅作复杂几何的起草草稿。
- **references/**：103 个 API 分页、8 个组件 recipe（楼梯/屋顶/窗/女儿墙/阳台）、13 个可运行 flows、6 份方法论参考（SKD_OVERVIEW / MODELING_WORKFLOWS / DESIGN_JSON_SCHEMA / SPATIAL_QUALITY 等）。
- **templates/**：可复制的完整示例脚本（如 `build_skeleton.py` 最小模型）。
- **requirements.txt**：运行 flows 需要的 Python 依赖（`ifcopenshell` / `ifcquery` / `numpy`，PyPI 官方发布，无本地源码依赖）。

skill 结构源自仓库历史中的 SimpleCADAPI skill 设计解剖（`research/ifc/simplecadapi_skill_anatomy.md`），并按 IFC 领域重写：**按动作拆模块、四层渐进展开、每层单一职责、MUST 条款串联**。

### 用 aiifc 建模型（AI 视角）

agent 加载 skill 后，按 Pipeline 顺序用 `ifcopenshell.api.run(...)` 写代码：

```
Skeleton（Project→Site→Building→Storey）
  → Elements（墙/板/梁柱，entity + placement + representation + container）
  → Openings（洞口 + 门窗填充）
  → Data（类型 / 材质 / 属性集）
  → Export（model.write + ifcopenshell.validate）
```

复杂户型 / 异形 / 多楼层先输出 **design JSON**（几何意图，不写坐标），经 `design_builder.py` 规范化后再生成构建脚本——避免坐标漂移。

## aiplan（plan 阶段：外部资料 → 任务书）

`skills/aiplan/` 是管线**入口** skill：把外部资料（图片/PPT/技术文档/用户对话）归一为下游可执行的建筑实施方案，并与用户自然语言交互确认设计意图（四轮渐进：骨架→几何→功能→结构空间，全程用 `question` 工具弹框确认）。**不画 DXF、不写 IFC、不做坐标级布局**。

**输入**：无特殊要求——任何形态的外部资料与用户描述（step-00 摄取归一化 → 意图卡片）。

**输出**——schema 事实源在包内 `references/schemas/`，即以下两个文件：

| 输出 | 契约事实源 | 去向 |
|---|---|---|
| `plan.json`（任务书：要什么 / 在哪盖 / 什么规范） | `skills/aiplan/references/schemas/plan.schema.json` | 下游 cad（aidxfv v3 只读） |
| `bim_supplement.json`（CAD 覆盖不了的 BIM 补充：屋顶 / 特殊结构 / PSET） | `skills/aiplan/references/schemas/bim_supplement.schema.json` | 下游 bim |

- **落盘**：成对产出，`aiplan land <plan> <bim> --outdir <dir>` 落 `{workspace}/plan/`，过门禁（`aiplan validate` / `aiplan gate`）+ canon sha256 互指。
- **自包含**：schema / 金样 / 词表 / 类型包全部内联在包内，仅依赖 `jsonschema`，独立可迁移，零跨 skill 运行时依赖。

## aidxfv v3（plan→cad 正式版）

`skills/aidxfv/v3/` 是 CAD 生成的**正式版框架**——**后续迭代都在这个框架上进行**（`v1` 通用 DXF / `v2` 建筑平面管线为遗留演进，不再作为迭代基线）。

**输入**：
- `plan.json`（aiplan 落盘的任务书，**只读**，全程不改）
- 用户额外描述（需求补充）

**输出**：

| 输出 | 说明 |
|---|---|
| `building.json` | 工程图纸 + bim 接口（供下游 bim 消费） |
| 各层 `floor.dxf` | 逐层平面绘制图（可交付图纸） |

**分工（LLM 设计 × 机器锚定）**：LLM 声明 `skeleton.json`（骨架：分区/核心筒/走廊/切割线/blocks）与 `rooms.json`（房间：承接分区/画墙/标签）——只说哪里/多大/邻着谁，**坐标交给机器**；派生/锚定/校验/渲染/检索全机器，`aidxfv3 normalize` 是唯一坐标计算点。

**pipeline（S0-S4）**：`preprocess`（plan.json → derived/ → 断点⓪）→ `skeleton`（断点①）→ `rooms`（断点②）→ `details`（门窗统一规律 + 柱网 + 标注）→ `deliver`（building.json + 逐层 DXF + 封存 rooms）。断点用 `question` 工具确认；多 zone（异楼层裙房/塔楼）独立 mission 并行，`aidxfv3 state` 编排 + 中断恢复。

**契约事实源**：`references/schemas/`（plan 副本 / skeleton / rooms / building，**schema 即事实源**）；机器命令的输入输出 schema / 边界行为 / 退出码见 `references/machine_contract.md`。

**依赖**：`ezdxf` + `shapely`（见包内 `requirements.txt`），自包含零跨 skill 运行时依赖。

## 安装到你的 agent

skill 是 agent 无关的目录包，任何支持 Agent Skills 规范的 agent（opencode、Claude Code、Cursor 等）都能加载：

```bash
# 1) 从仓库复制或解压分发包
cp -r skills/aiifc ~/.config/opencode/skills/aiifc
# 或用打包器生成 tar.gz 分发包
python tools/skill_pack.py --archive   # 产出 skills/dist/aiifc.tar.gz（默认 skill：aiifc）
python tools/skill_pack.py --skill-dir skills/aiplan --archive        # aiplan
python tools/skill_pack.py --skill-dir skills/aidxfv/v3 --archive     # aidxfv3
tar xzf skills/dist/<name>.tar.gz -C ~/.config/opencode/skills/

# 2) 安装运行依赖（各 skill 包内 requirements.txt）
uv pip install -r skills/aiifc/requirements.txt        # aiifc
uv pip install -r skills/aiplan/requirements.txt       # aiplan
uv pip install -r skills/aidxfv/v3/requirements.txt    # aidxfv3
```

## 与平台 REST API 的关系

| 方式 | 场景 | 入口 |
|---|---|---|
| **REST 编辑 API** | 在既有脚本上定向修改（PARAMS 暂存 / edit-call 标量改写）、版本与 diff | `:8100/models/{id}/...`（IFC，见 [AI 接入](/reference/ai)） |
| **aiifc skill** | 从零建 IFC 模型、大改几何、复现上传 IFC（bootstrap），产出契约化构建脚本 | agent 直接写 Python（`ifcopenshell.api`） |
| **aiplan / aidxfv v3 skill** | plan→cad 全链路：外部资料归一为任务书，任务书落地为逐层 DXF + building.json | agent 直接跑 `aiplan` / `aidxfv3` 命令 |

两者互补：skill 负责「生成 / 大改」，平台的沙箱执行 / 版本 / XKT 重转链路负责「落盘与追踪」。

## 分发与打包

- 打包器：`tools/skill_pack.py`（泛化：校验 SKILL.md frontmatter / 必需路径 / 无噪声，复制到 `skills/dist/`，可选打 tar.gz）。`--skill <name>` 默认 `aiifc`；`--skill-dir <path>` 可打任意 skill 目录（aiplan / aidxfv3 走此路径）。
- 产物 agent 无关：`SKILL.md` + `references/` 即 Anthropic Agent Skills 规范。
- CI（`skill (aiifc pack + flows smoke)` job）会在每个 PR 校验打包产物完整性并跑 flows 冒烟。

## 许可

- `skills/aiifc/` 声明为 **LGPL-3.0**（`SKILL.md` frontmatter `license` 字段）。文档参考自 [IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) 官方文档（LGPL-3.0）。
- `skills/aiplan/` 与 `skills/aidxfv/v3/` 声明为 **MIT**。
