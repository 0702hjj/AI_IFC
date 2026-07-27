# AI + IFC 技术地图（Tech Map）

> 本项目目标：**AI 读取 / 修改 / 生成 IFC**。
> 本文不定位于生态综述，而是明确四个核心技术决策：
> ① 输入隔离层 ② Tool Function 层（可演进为 MCP）③ 前端双方案 ④ RAG。
> SimpleCADAPI 仅作为设计模式参考。

---

## 1. 输入隔离层（Intent Isolation Layer）

### 1.1 原则

> **用户原始输入不直接进入 LLM。** 中间必须有隔离层，负责确定需求、构造 LLM 的输入。

不推荐：

```
用户输入 ──────────────→ LLM → 工具调用
```

推荐：

```
用户输入
   |
   v
┌─────────────────────────────────────────────┐
│ Intent Isolation Layer（输入隔离层）          │
│  1. 意图分类：query / analyze / modify / generate │
│  2. 需求澄清：缺参数时向用户追问，而非让 LLM 猜     │
│  3. 上下文组装：注入 RAG 检索结果 + 工具清单 + 约束  │
│  4. 安全检查：过滤越权请求（如无权限的 modify）      │
└──────────────────┬──────────────────────────┘
                   | 结构化意图（Structured Intent）
                   v
                  LLM
                   |
                   v
             Tool 调用
                   |
                   v
┌─────────────────────────────────────────────┐
│ Output Validator（输出校验，回流隔离层）        │
│  结果合理性检查 / 错误结构化 / 必要时触发重新规划  │
└─────────────────────────────────────────────┘
```

### 1.2 隔离层职责拆解

**a) 意图分类**：先用轻量分类器（规则 + 小模型）把请求路由到固定管线，而不是把所有请求都丢给 LLM 自由发挥：

| 意图 | 示例 | 后续管线 |
|---|---|---|
| query | "三层有哪些墙？" | Tool Function（Function Calling） |
| analyze | "分析楼层面积效率" | 沙箱代码执行 |
| modify | "把门高改为 2.1m" | 修改计划 → Diff → 人工确认 |
| generate | "创建 20m×30m 两层办公楼" | BIM IR → 编译 → 校验 |

**b) 需求澄清**：隔离层维护必填参数 schema。例如 modify 意图必须确定「目标元素集 + 属性 + 新值 + 确认人」，缺项则生成追问，**凑齐前不调用 LLM**：

```
用户: "把门改高一点"
隔离层: 缺少 [目标范围] [具体数值] →
        追问: "修改哪些门（全部/某楼层）？目标高度是多少？"
```

**c) 上下文组装**：LLM 的输入由隔离层确定性拼装，包括：

```json
{
  "intent": "query",
  "model_context": {"schema": "IFC4", "storeys": ["L1","L2","L3"], "stats": {...}},
  "schema_context": "<RAG 检索到的相关实体/属性集定义>",
  "tools": ["find_elements", "get_properties", ...],
  "constraints": ["只读", "结果需附 GUID", "禁止推测未返回的数据"],
  "user_request": "三层有哪些混凝土墙？"
}
```

**d) 价值**：LLM 行为边界由隔离层而非 prompt 约束保证——可测试、可审计、可加权限；用户输入的随意性被挡在系统之外。

---

## 2. Tool Function 层（AI 读取 IFC 的工具集）

### 2.1 原则

- LLM 不直接操作 IFC，也不直接调用 IfcOpenShell，而是调用**受控工具**
- 工具是确定性的：可单测、类型化、有权限边界
- 工具错误返回结构化引导（`possible_causes / how_to_fix`），支持 Agent 自我修正——参考 SimpleCADAPI `errors.py` 的 `ErrorGuidance` 设计

### 2.2 第一批工具（Read 集，MVP 范围）

```python
# 元素查询
find_elements(type="IfcWall", storey="Level 3", where={"material": "Concrete"})
  -> [{"guid": "3xA91", "name": "External Wall", ...}]

# 属性访问
get_properties(guid="3xA91", pset="Pset_WallCommon")
  -> {"FireRating": "120min", "LoadBearing": true}

# 空间关系
get_containment(guid="3xA91")
  -> {"storey": "Level 1", "building": "...", "path": [...]}
get_related_elements(guid, relationship="contained_in" | "connected_to" | "voids")

# 数量/几何计算
calculate_quantity(type="IfcWall", quantity="area" | "volume", filter={...})
  -> {"value": 2350.0, "unit": "m2", "element_count": 42}

# 模型元信息
get_model_summary()
  -> {"schema": "IFC4", "storeys": [...], "type_counts": {...}, "quality_flags": [...]}
```

设计要点：

1. **返回 JSON + GUID**：所有结果带 GUID，供前端定位高亮，也供后续工具链式调用
2. **where 子句可序列化**：查询条件用可序列化 DSL 表达（参考 SimpleCADAPI 的 `ShapeSelector.to_dict/from_dict`，ql.py:398-687），便于审计、缓存、重放
3. **权限分层**：工具注册表区分 `read / modify / admin`，MVP 只暴露 read

### 2.3 演进路径：Tool Function → MCP

工具层按 MCP（Model Context Protocol）语义设计，一期作为内部 Function Calling，二期直接包装为 MCP Server，无需重写：

```
一期:  LLM → Function Calling → Tool Layer → IfcOpenShell
二期:  LLM → MCP (标准协议)   → IFC MCP Server → IfcOpenShell
              ifc.find_elements / ifc.get_properties /
              ifc.query_relationships / ifc.calculate_quantity
```

为此，工具定义需从一开始就满足：无会话状态隐式依赖、参数 JSON Schema 化、错误结构化、单次调用幂等（read 集天然满足）。

---

## 3. 前端方案：两套路线并存，由用户/场景选择

两条路线都可行，架构上前端通过统一的后端 API 取数据，viewer 层可替换。

### 3.1 方案 A：xeokit + React

```
IFC → 后端解析 → XKT（xeokit 压缩格式）→ xeokit Viewer
```

| 维度 | 评估 |
|---|---|
| BIM 语义 | ★★★★★ 原生理解 IFC 类型/属性树，开箱即用的对象拾取-语义联动 |
| 大模型性能 | ★★★★★ XKT 格式专为超大 BIM 优化，千万级构件可流畅渲染 |
| 开发成本 | 低，BIM 常用交互（剖切/隔离/属性面板）内置 |
| 灵活性 | 中，定制渲染能力受 xeokit API 约束 |
| 适合 | 企业级平台、大模型审查场景、MVP 快速落地 |

### 3.2 方案 B：Three.js + web-ifc

```
IFC → web-ifc（WASM，浏览器端解析）→ Three.js 场景
```

| 维度 | 评估 |
|---|---|
| BIM 语义 | ★★★ web-ifc 提供 IFC 解析与属性访问，语义-几何联动需自建 |
| 大模型性能 | ★★★ 需自行做 LOD/实例化/分块加载优化 |
| 开发成本 | 高，但每一层可控 |
| 灵活性 | ★★★★★ Three.js 生态大，可做定制可视化（热力图、分析叠加层） |
| 适合 | 轻量产品、需要深度定制渲染/分析可视化的场景 |

### 3.3 选择建议

- **MVP / 企业平台 → 方案 A（xeokit）**：目标不是 3D 引擎而是 AI BIM，不在 viewer 上消耗研发
- **需要自定义分析可视化（如空间效率热力图）→ 方案 B**
- 架构保证：**后端输出统一的元素 JSON（GUID + 属性 + 几何引用），两套 viewer 共用同一 API**，Agent 的 `find_elements` 结果可直接驱动任一 viewer 高亮定位

---

## 4. RAG（IFC Schema 知识库 + 检索）

### 4.1 为什么必须做

IFC4 约 800+ Entity、数千属性、大量关系，无法整体塞进 LLM 上下文；且不同软件导出的 IFC 用词习惯不同。隔离层组装上下文时（§1.2c），`schema_context` 必须由检索提供。

### 4.2 知识库内容

```
IFC Schema 知识
  ├─ Entity 定义:      IfcWall / IfcDoor / IfcSpace ...（描述、属性清单）
  ├─ Property Sets:    Pset_WallCommon(FireRating, LoadBearing) ...
  ├─ 关系模板:          Wall → has opening → Door; Space → contained in → Storey
  └─ 项目语料:          当前模型的实际 pset 名、storey 命名、类型分布
规范/业务知识
  └─ 消防/规范条目（用于 Review/检查类意图）
```

### 4.3 检索流程

```
用户请求
   |
   v
隔离层意图分类
   |
   v
Retriever ──────────────────────────┐
   |                                 |
   ├─ 向量检索: pgvector 语义相似       |
   |   ("防火门" → IfcDoor + Pset_DoorCommon.FireRating)
   |                                 |
   └─ 图检索: 关系模板展开              |
       ("三层" → IfcBuildingStorey → containment 路径)
   |                                 |
   v                                 v
拼装 schema_context → 注入 LLM 输入（§1.2c）
```

### 4.4 技术选型

- **存储**：PostgreSQL + pgvector，一份数据库同时存元素索引（Element/Property/Relation 表）和语义 embedding，避免多一套向量库
- **混合表示**：属性数据走关系库，空间关系走图查询——是当前主流研究方向，也匹配 IFC 的双重结构
- **冷启动**：先灌 IFC4 官方 schema 定义；每个上传模型完成解析后，把该模型的实际 pset/命名习惯增量入库（解决"不同软件 IFC 质量差"问题）
- **语义缓存**：检索结果与查询结果按 (模型版本, 意图, 参数) 缓存，大模型（500MB+ IFC）场景避免重复解析与重复推理

---

## 5. 补充决策

### 5.1 修改/生成的安全闭环（非本期，但接口预留）

```
modify 意图 → 生成修改计划(JSON) → Diff Preview → 人工确认 → 事务执行 → IFC 校验
```

修改计划与 BIM IR 均为可序列化 JSON——参考 SimpleCADAPI 的 model.json + replay 模式（serializer.py），diff/审计/重放都建立在可序列化 IR 之上。

### 5.2 后端分层

```
React 前端 (viewer A/B 可替换)
   |
API Gateway
   |
Intent Isolation Layer  ── RAG Retriever (PostgreSQL+pgvector)
   |
LLM Agent (Function Calling / 二期 MCP)
   |
Tool Function Layer
   |
IfcOpenShell → IFC / PostgreSQL 索引
```

### 5.3 路线图

| 阶段 | 交付 |
|---|---|
| 0-3 月 | 隔离层 + 意图分类；Read 工具集（§2.2）；RAG 冷启动；xeokit MVP |
| 3-6 月 | MCP Server 化；modify 闭环（Diff + 人工确认）；方案 B viewer 备选 |
| 6-12 月 | BIM IR + 生成编译器；规范知识库接入 Review 场景 |
