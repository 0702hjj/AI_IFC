# AI Skill 获取与安装

> 平台的 AI 生成能力以 **skill 包**形式交付：一个 skill 就是一个目录，内含 `SKILL.md`（入口说明）+ 参考文档/脚本，装进 agent 运行时即可驱动 AI 生成 IFC 或 CAD（DXF）。skill 与平台其余组件解耦——不部署本平台也能单独使用。

## 有哪些 skill

| skill | 用途 | 许可证 |
| --- | --- | --- |
| `aiifc` | IFC 生成/修改（IfcOpenShell 参考文档包） | LGPL-3.0 |
| `aidxfv1` | 通用 CAD/DXF 生成（fork 自 earthtojake/text-to-cad，运行时 vendored 自包含） | MIT |
| `aidxfv2` | 建筑平面管线（plan.json 对齐 → 草案 → 逐层 DXF） | MIT |
| `aiblueprint-mcp` | DXF 交互微调 MCP server（检查/编辑/测量/预览） | MIT |
| `aibim-orchestrator` | 主 Agent 编排提示词包（意图路由 + 子 Agent 分工契约 + plan→cad→ifc 接力数据契约） | Apache-2.0 |

每个 skill 的变更记录见包内 `CHANGELOG.md`，当前版本均为 `0.1.0`。

## 下载

从 GitHub Release 页面下载 `<name>-<version>.tar.gz`（如 `aiifc-0.1.0.tar.gz`）；或在仓库内自助打包：

```bash
python tools/skill_pack.py --skill aiifc --archive
python tools/skill_pack.py --skill aidxfv1 --skill-dir skills/aidxfv/v1 --archive
```

产物在 `skills/dist/`。

## 安装

解压到 agent 运行时的 skill 目录：

- **opencode**：用户级 `~/.agents/skills/<name>/`，或项目级 `<项目>/.opencode/skill/<name>/`（单数 `skill`）
- **Claude Code**：`~/.claude/skills/<name>/`

安装后 `SKILL.md` 的 `name`/`description` 会被运行时自动索引，无需额外注册。

## 运行依赖

- **aiifc**：Python 环境装 `ifcopenshell` / `ifcquery` / `numpy`（见包内 `requirements.txt`）；与 `services/ifc` 编辑服务配对使用时见 [services/ifc 独立部署](/guide/services-ifc)。
- **aidxfv1 / aidxfv2**：Python 环境装 `ezdxf` 等（见包内 `requirements.txt`）。
- **aiblueprint-mcp**：MCP server 形态，依赖见包内 `requirements.txt`，按包内 README / opencode.json 接入。

## 与平台的关系

skill 是「AI 侧」入口（agent 直接写构建脚本/调用工具）；`services/ifc` 是「服务端」运行时（沙箱执行、版本快照、语义 diff）。两者配对但各自可独立获取与部署——只用 skill 做一次性生成不需要平台；要用版本/diff/双角色编辑 API 才需要部署 [services/ifc](/guide/services-ifc)。
