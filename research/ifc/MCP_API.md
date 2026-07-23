# ifcopenshell 的 MCP(模型上下文协议)接口调研

日期:2026-07-22
研究问题:是否存在封装 ifcopenshell、供大模型(LLM Agent)操作 IFC 模型的 MCP 接口?
结论速览:**有,且官方自带** —— IfcOpenShell 源码内置 `ifcmcp`(PyPI 包 `ifcopenshell-mcp`),
30+ 个工具覆盖加载/查询/校验/出图/渲染/几何构建/API 编辑全流程;社区另有若干基于
Bonsai/IfcTester 的专项 MCP 项目。

---

## 1. 官方方案:ifcmcp(源码内置,重点)

**位置**:已下载源码 `/CADapi/IfcOpenShell/IfcOpenShell-0.8.0/src/ifcmcp/`
**安装**:`pip install ifcopenshell-mcp`(运行服务需 `pip install ifcopenshell-mcp[mcp]`)
**许可证**:LGPLv3+
**架构**:包装 `ifcquery`(查询)+ `ifcedit`(编辑),IFC 模型常驻内存,多步编辑会话间无文件 I/O。
**传输**:stdio(适配 Claude Code 及任意 MCP 客户端)。

### 1.1 接入配置

```bash
ifcmcp                                   # 启动 stdio 服务
claude mcp add --transport stdio ifc -- ifcmcp   # Claude Code 注册
```

或项目根 `.mcp.json`:

```json
{ "mcpServers": { "ifc": { "type": "stdio", "command": "ifcmcp" } } }
```

### 1.2 工具清单(31 个,分 7 类)

**会话管理(4)**
| 工具 | 作用 |
|---|---|
| `ifc_new` | 新建空模型(默认 IFC4,可选 IFC4X3) |
| `ifc_load` | 加载 .ifc 到内存(返回 schema 与实体数) |
| `ifc_save` | 写回磁盘(空路径覆盖原文件) |
| `ifc_reset` | 卸载释放会话 |

**查询(13)**
| 工具 | 作用 |
|---|---|
| `ifc_summary` | 模型总览:schema/实体计数/项目信息 |
| `ifc_tree` | 完整空间层级树(Project→Site→Building→Storey→构件) |
| `ifc_info` | 按 step ID 深查:属性/pset/类型/材质/容器/4x4 定位矩阵 |
| `ifc_select` | ifcopenshell selector 语法过滤(如 `IfcWall`) |
| `ifc_relations` | 元素全部关系;`traverse="up"` 回溯到 IfcProject |
| `ifc_contexts` | 几何表达上下文列表 |
| `ifc_materials` | 材质/材质集及其被赋值的构件 |
| `ifc_clash` | 碰撞/净距检查(clearance/tolerance/scope 参数) |
| `ifc_validate` | schema 与约束校验(可开 express_rules) |
| `ifc_schedule` / `ifc_cost` | 进度计划/造价清单树(`max_depth` 截断防爆) |
| `ifc_schema` | 按模型 schema 版本返回 IFC 类文档(描述/预定义类型/属性说明) |
| `ifc_quantify` | QTO 工程量计算(IFC4/IFC4X3 QtoBaseQuantities),写回 IfcElementQuantity |

**出图与渲染(2)**
| 工具 | 作用 |
|---|---|
| `ifc_plot` | 2D 技术图(平面/立面/剖面,比例/图纸尺寸可调),返回内联 PNG 供 LLM 查看,可存 SVG;依赖 `ifcopenshell.draw` |
| `ifc_render` | 3D 渲染 PNG(等轴/顶/四向视图,支持元素高亮),依赖 pyvista + C++ 几何绑定 |

**ShapeBuilder 几何构建(3)**
| 工具 | 作用 |
|---|---|
| `ifc_shape_list` | 列出全部 ShapeBuilder 方法 |
| `ifc_shape_docs` | 查看某方法完整文档 |
| `ifc_shape` | 执行几何构建(如 `extrude`,params 为 JSON,实体按 step ID 解析) |

**编辑发现(2)** —— 让 LLM 自助探索 API
| 工具 | 作用 |
|---|---|
| `ifc_list` | 列出全部 34 个 API 模块 / 模块内函数 |
| `ifc_docs` | 查看某 API 函数的参数/类型/默认值/说明 |

**编辑执行(1)**
| 工具 | 作用 |
|---|---|
| `ifc_edit` | 执行任意 `ifcopenshell.api` 变更函数(params 为 JSON 字符串,带类型强转:实体按 ID 解析、`"5,6,7"`→实体列表、`"true"`→bool、`"none"`→None);不自动保存,需配 `ifc_save` |

### 1.3 设计亮点(对 Agent 友好)

- **发现-文档-执行三段式**:`ifc_list` → `ifc_docs` → `ifc_edit`,LLM 无需预置 API 知识即可自助操作整个 api 面
- **视觉反馈闭环**:`ifc_plot`/`ifc_render` 返回内联 PNG,LLM 可"看到"编辑结果再决策
- **状态会话**:模型常驻内存,编辑链快;显式 `ifc_save` 防止误写
- **截断约定**:schedule/cost 大树用 `max_depth` + `{"truncated": true, "count": N}`,防止上下文爆炸

### 1.4 典型工作流(README 推荐)

`ifc_load` → `ifc_summary/tree/select/info/relations` 检查 → `ifc_validate` →
`ifc_schema` 查类文档 → `ifc_list/ifc_docs` 找函数 → `ifc_edit` 编辑 →
`ifc_quantify` 算量 → 查询工具复核 → `ifc_save`

---

## 2. 社区方案(GitHub 搜索 "ifcopenshell mcp",5 个结果)

| 项目 | Stars | 说明 |
|---|---|---|
| vinnividivicci/ifc-ids-mcp | 26 | 用 IfcTester **确定性生成 IDS**(信息交付规范)文件的 MCP,专注标准校验场景 |
| lfniederauer/blender-agentic-bonsai-sketcher-mcp | 2 | 扩展 Blender MCP,把 Bonsai/ifcopenshell 的 `bim_*` 工具暴露为 streamable HTTP MCP + Docker 部署 + ADK agent |
| Show2Instruct/bonsai-mcp | 1 | MCP 桥接 Claude/Cursor 到**运行中的 Blender + Bonsai 会话**(GUI 内交互建模) |
| Braldan1/open-bim-ai-stack | 0 | 基于开放标准的厂商无关 BIM+LLM 工作流集合 |
| ProfRino/bonsai-bim-skills | 0 | Claude Code skills(非 MCP):7 个面向墙/洞口/屋顶/楼梯的 IFC 建模技能 |

**格局**:官方 `ifcmcp` 是唯一"纯 ifcopenshell、无 GUI 依赖、全功能"的 MCP;
社区项目多走 Blender/Bonsai 桥接(GUI 可视化 + Agent)或 IDS 等专项。

---

## 3. 与本项目流水线的结合点

```
DXF → cad-to-shapely → ifcopenshell 建模 → model.ifc
                                        ↓
                         ifcmcp(stdio)暴露给 LLM Agent
   ├─ 校验:ifc_validate / ifc_clash / ifc_schema
   ├─ 审查:ifc_summary / ifc_tree / ifc_plot(平面出图,PNG 回读)
   ├─ 增强:ifc_edit(pset 属性、材质)、ifc_quantify(工程量)
   └─ 闭环:Agent 依据 render/plot 图像反馈迭代修改 → ifc_save
```

对 "DXF 生成单层建筑" 的场景,ifcmcp 正好补上"生成后由 LLM 检查/修复/丰富语义"的环节;
且其发现式编辑(`ifc_list/ifc_docs/ifc_edit`)意味着我们的建模脚本与 Agent 修正
使用的是**同一套 `ifcopenshell.api`**,行为一致。

## 4. 选型建议

| 需求 | 选择 |
|---|---|
| 无头(headless)批量/服务器端 LLM 操作 IFC | **官方 ifcmcp**(stdio,纯 Python 依赖) |
| 需要 LLM 看到真实 BIM 视口交互 | bonsai-mcp(桥接 Blender+Bonsai) |
| 只做 IDS 标准校验文件生成 | ifc-ids-mcp |

## 5. 参考

- ifcmcp 源码与 README:`/CADapi/IfcOpenShell/IfcOpenShell-0.8.0/src/ifcmcp/`
- PyPI:`ifcopenshell-mcp`
- 测试用例(工具行为参考):`src/ifcmcp/tests/`(test_query/test_edit/test_shape/test_server/test_session)
