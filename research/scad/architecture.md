# AI_IFC（SimpleCADAPI）项目架构与运行逻辑

> 本文整理自架构分析对话，汇总项目的整体分层架构、关键子系统与核心运行逻辑（调用链与 replay 机制）。

## 项目定位

**SimpleCADAPI**（本仓库 AI_IFC 的核心 SDK）是一个 **OCP-native（OpenCascade 原生）的 Python CAD 建模 SDK**，专为「**AI agent 生成 CAD 模型**」这一场景设计——从错误类型（`errors.py` 带 LLM 导向的 `ErrorGuidance`）、到自带 Agent Skill 包（`skills/`）、到强制 API 契约的 `SKILL.md`，整个 SDK 原生服务 LLM 场景。

- 版本：`2.0.1b1`（beta），许可证 AGPL-3.0
- 依赖：`numpy` / `rich` / `cadquery-ocp`（核心三件套），`python-fcl`（可选碰撞检测），**FreeCAD 不是依赖**（仅作为可选的 `.FCStd` 导出后端，通过 subprocess 调用外部 `FreeCADCmd`）

---

## 整体分层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Agent 层  skills/simplecadapi/                              │
│    SKILL.md (17 条 MUST 规则) + references/docs (API 契约文档)  │
│    → 让 LLM 生成 CAD 代码时遵守正确 API 签名                    │
├─────────────────────────────────────────────────────────────────┤
│  应用/示例层  examples/  (01~20)                                │
│    基础建模/图回放/表达式/齿轮/装配/减速器/BLDC 执行器          │
├─────────────────────────────────────────────────────────────────┤
│  标准件库 std/         │  验证器 verifier/        │ 错误系统    │
│   gear.py (9 函数)     │   check_collision        │ errors.py   │
│   bearing.py (装配)    │   (python-fcl)           │ (LLM 导向) │
├─────────────────────────────────────────────────────────────────┤
│  产品语义层  product.py                                         │
│   Part → Component → Assembly + Connector + Constraint(6类)     │
│   Material / Placement / solve_assembly_constraints             │
├─────────────────────────────────────────────────────────────────┤
│  公共建模 API  operations.py (7144 行, 113 个公共函数)          │
│   primitive / profile / feature / boolean / transform /         │
│   pattern / fillet/chamfer/shell / tag / sketch / assembly      │
├─────────────────────────────────────────────────────────────────┤
│  参数化 / 历史 / QL 层                                          │
│   expr.py(Var/Const)  graph.py(GraphSession)  frame.py(Frame)   │
│   topology.py(OperationGraph DAG)  ql.py(ShapeSelector)         │
│   tracking.py(OCC 历史追踪)  tagging.py / autotag.py            │
├─────────────────────────────────────────────────────────────────┤
│  序列化 / 翻译层                                                │
│   serializer.py (model.json IR + replay 引擎 ~980 行)           │
│   translator/freecad_translator/ (可选 .FCStd 后端)             │
├─────────────────────────────────────────────────────────────────┤
│  内部基础设施  core.py (1055 行) + kernel/ (10 个 OCP 封装)     │
│   Solid/Face/Wire/Edge/Vertex + _mesh.py + math.py(B 样条)      │
├─────────────────────────────────────────────────────────────────┤
│  外部内核  cadquery-ocp (OpenCascade) + numpy                   │
└─────────────────────────────────────────────────────────────────┘

开发者工具 auto_tools/（横切）:
  auto-docs-gen / make-export / evolve / skill-pack → 4 个 CLI
```

---

## 关键子系统

### 1. 几何引擎层（kernel/ + core.py）

三层清晰分离：

| 层 | 文件 | 特征 |
|---|---|---|
| **kernel/** | `ocp_*.py`（10 个模块） | 纯函数、无状态、直接映射 OCP，返回裸 `TopoDS_*` |
| **core.py** | `Vertex/Edge/Wire/Face/Solid/Compound` | 有状态包装类，持 `.wrapped`(OCP 对象) + 标签 + 元数据 + 拓扑父子树 |
| **operations.py** | 113 个公共函数 | 叠加坐标系变换、错误处理、图记录、标签、拓扑追踪 |

**core.py 的拓扑类型层次**（`core.py:493-1055`）：

```
TaggedMixin + TopoMixin
   ├─ Vertex   (level=0, 包装 TopoDS_Vertex)
   ├─ Edge     (level=1, 包装 TopoDS_Edge)
   ├─ Wire     (level=2, 包装 TopoDS_Wire)
   ├─ Face     (level=3, 包装 TopoDS_Face)
   ├─ Solid    (level=4, 包装 TopoDS_Solid)
   └─ Compound (level=5, 包装 TopoDS_Compound)

AnyShape = Union[Vertex, Edge, Wire, Face, Solid, Compound]
```

**kernel 内部依赖图**（唯一例外：`ocp_transforms` 反向依赖 core，因为变换后要按类型重新包装）：

```
ocp_features → ocp_curves
ocp_mesh → ocp_properties, ocp_topology
ocp_properties → ocp_topology
ocp_transforms → ..core  (反向依赖)
```

### 2. 命名约定：`_rXXX` 后缀

后缀编码返回类型契约（`r` = returns），让过程式 API 自文档化：

| 后缀 | 返回类型 | 数量 | 示例 |
|---|---|---|---|
| `_rsolid` | `Solid` | 71 | `make_box_rsolid`, `cut_rsolid`, `fillet_rsolid` |
| `_rface` | `Face` | 32 | `make_circle_rface`, `make_2d_cut_rface` |
| `_rwire` | `Wire` | 39 | `make_segment_rwire`, `make_polyline_rwire` |
| `_redge` | `Edge` | 36 | `make_line_redge`, `make_spline_redge` |
| `_rsketch` | `Sketch` | 92 | `make_sketch_rsketch`, `constrain_*_rsketch` |
| `_rassembly` | `Assembly` | 53 | `make_assembly_rassembly`, `solve_assembly_constraints_rassembly` |

### 3. QL 查询语言（ql.py）

- **`ShapeSelector`**（`ql.py:398-687`）：不可变构建器 AST，**可序列化**（`to_dict/from_dict`），可嵌入操作 DAG，用于图重放时的几何选择。
- **`Query`**（`ql.py:974-997`）：即时求值管道，类似 LINQ-to-Objects。

DSL 示例：

```python
edges().where(curve_type("circle")).order_by(center_axis("z")).take(1).exactly(1)
```

谓词系统：`tag/meta/prop/curve_type/surface_type/op/origin/role/and_/or_/not_`，全部可序列化。属性路径解析器（`ql.py:57-262`）理解 `geom.center.x`、`topo.kind`、`meta.*` 等丰富路径，支持第三方注册扩展。

### 4. 草图约束求解器（sketch.py）

真正的声明式参数化 2D 草图求解器：

- **22 种约束**：fix / coincident / horizontal / vertical / parallel / perpendicular / collinear / equal_length / equal_radius / distance / distance_x / distance_y / length / radius / diameter / angle / point_on / concentric / midpoint / tangent / symmetric
- **求解器**（`sketch.py:843-1199`）：阻尼高斯-牛顿法 + 有限差分雅可比矩阵 + 回溯线搜索，自由度分析，状态分类（solved / underconstrained / conflicting / redundant）
- **物化**：`make_wire()` / `make_face()` 把求解后的草图转为 OCC `Wire` / `Face`

### 5. 产品/装配层（product.py）

```
Material → Part(单实体) → Component(实例+位姿) → Assembly
                                         │
                    Connector(face/edge/vertex/placement 锚点)
                    Constraint(6类: fixed/revolute/prismatic/gear/belt/rack_pinion)
                    solve_assembly_constraints (约束求解)
```

`Assembly` 是不可变 dataclass，用 `with_component` / `with_constraint` 链式构建。

### 6. 标准件库（std/）

完全基于公共 API 构建的参数化机械零件库：

- **`gear.py`**（1635 行，9 个函数）：直齿/斜齿/人字齿轮、内齿圈、摆线针轮盘、齿条——全部用约束草图 + B 样条渐开线齿面 + ruled loft（斜/人字齿）实现
- **`bearing.py`**：球轴承，返回 `Assembly`（外圈/内圈是旋转副语义）

### 7. AI Agent Skill 包（skills/）

- **`SKILL.md`**：agent 行为契约，17 条 MUST 规则（强制 keyword 参数、布尔必须返回单个 Solid、优先 stdlib 标准件、用 model.json 做 interchange 等）
- **`references/docs/`**：完整 API 文档镜像，每个公共函数一页 markdown
- 由 `skill-pack` 脚本生成，只打包文档不打包 SDK 源码

### 8. 开发者工具（auto_tools/）

4 个 CLI 脚本（`pyproject.toml:88-92`）：

| 命令 | 用途 |
|---|---|
| `auto-docs-gen` | 从源码 AST 生成 `docs/api/*.md` 和 `docs/stdlib/*.md` |
| `make-export` | 重新生成 `__init__.py` 导出清单 |
| `evolve` | 把新函数实现追加到 `evolve.py`（AI 进化机制） |
| `skill-pack` | 打包 Agent Skill bundle 到 `skills/` |

---

## 核心运行逻辑

### 1. 无侵入双写架构（可重放建模图）

用户调用普通建模函数时，几何计算与图记录并行发生：

```
用户调用 make_box_rsolid(10, 20, 30)
        │
   ┌────┴────┐
   ▼         ▼
几何计算    图记录
(OCP kernel)  record_operation_if_active()
→ TopoDS    → session.graph.add_node(...)
                ↓ attach_graph_node()
              把节点血缘贴到 shape._runtime["graph.node"]
                ↓
              返回的 Solid 既是真实几何，又隐藏携带了图节点引用
```

三个关键机制：

1. **`GraphSession`**（`graph.py:49-91`）：基于 `contextvars.ContextVar` 的隐式会话，线程安全、可嵌套。用 `with GraphSession() as session:` 激活。
2. **`record_operation_if_active`**（`graph.py:289-339`）：无 session 时完全无副作用；有 session 时自动记录；`suspend_graph_recording()` 时静默（replay 引擎和内部组合用）。
3. **`_finalize_*` 辅助函数**（`operations.py:1204-1311`）：每个公共 API 尾部调用，统一附加追踪标签 + 记录到图。四个变体对应不同操作类型：`_finalize_primitive_shape` / `_finalize_primitive_solid` / `_finalize_derived_shape` / `_finalize_tracked_solid`（后者携带 `TopoDelta` 并调用 `apply_tracking_tags_to_delta`）。

**model.json 是 interchange 边界**：`GraphSession` 同时维护三张子图——`OperationGraph`(操作 DAG) + `ExpressionGraph`(参数表达式) + `FrameGraph`(坐标系快照)，序列化为 canonical `model.json`（schema_version="2.0"），可 `replay_model_json()` 重放，也可翻译到 FreeCAD。

### 2. 具体调用链：基础体创建（make_box_rsolid）

```
operations.make_box_rsolid(width, height, depth, bottom_face_center=...)
  → kernel/ocp_primitives.make_box_solid(corner, dx, dy, dz)
      → BRepPrimAPI_MakeBox(...).Build() → 裸 TopoDS_Solid
  → core.Solid 包装（.wrapped + 标签 + 元数据）
  → _finalize_primitive_solid(...)
      → _attach_track_summary(shape, op=...)
      → record_operation_if_active(op, params, outputs=shape, ...)
          → get_active_session() 为 None 或 suspend 深度 > 0 时直接返回
          → canonicalize_params()（若含表达式参数，记录到 ExpressionGraph）
          → session.graph.add_node(...)（建立 DAG 节点与输入边）
          → attach_graph_node(output, node, output_slot, graph_id)
              → output._set_runtime("graph.node", node) 等隐藏血缘
              → set_metadata("graph", {...})
              → _attach_topo_refs_recursive(...) 子形状级血缘
  → 返回 Solid
```

### 3. 具体调用链：布尔运算（cut_rsolid）与拓扑血缘

```
operations.cut_rsolid(body, tool, ...)
  → tracking.tracked_cut(body, tool)
      → BRepAlgoAPI_Cut()
          .SetRunParallel(True) / .SetUseOBB(True)
          .SetToFillHistory(True)        # ★ 显式开启 OCC 历史记录
          .SetArguments(body.wrapped) / .SetTools(tool.wrapped)
          .Build()
      → _build_boolean_result(...)
          → _query_history(...) 对每个子形状查询:
              IsDeleted → deleted
              Modified/Generated 为空 → preserved
              Modified 返回不同形状 → modified
              Generated 非空 → generated
              （并收集 section_edges）
          → 产出 TopoDelta（preserved/modified/generated/deleted/section_edges）
  → _finalize_tracked_solid(solid, delta=TopoDelta, ...)
      → apply_tracking_tags_to_delta(...) 按血缘打标签
      → record_operation_if_active(..., topo_delta=delta)
```

`autotag.py` 基于 `TopoDelta` 自动生成语义标签（如 `op.cut.modified`、`face.cut.generated`）。这让下游 fillet/chamfer 的选择能**跨越 boolean 操作精确追溯**到原始面——这是区别于普通"宏录制器"的关键。

### 4. Replay（重放）引擎运行逻辑

`replay_model_json(json_str)` → `import_model_json` → `_execute_graph(graph, leaf_ids)`（`serializer.py:1508-2491`，~980 行）：

1. **拓扑排序**：`graph.topological_order()`（Kahn 算法，`graph.py`，遇环抛 `ValueError`）
2. **防递归记录**：整个执行包裹在 `with suspend_graph_recording():` 中，replay 不会再次写入图
3. **逐节点执行**：
   - 若节点带 `context`（坐标系快照），用 `use_coordinate_system(node.context)` 恢复
   - 巨型 if/elif 按 `op_name` 分发到 `ops.*` 函数（如 `make_box_rsolid` → `ops.make_box_rsolid(params["width"], ..., bottom_face_center=tuple(...))`）
   - `ctx.require_params(...)` 校验必需参数
   - `_input_outputs(ctx, outputs, node, idx)` 从 `outputs` 字典取上游节点的缓存结果作为输入
4. **结果回贴**：`_store_outputs` 对每个输出调用 `attach_graph_node`（血缘回贴）后存入 `outputs[node_id]`
5. 失败时经 `raise_harness_error` 包装为带 `possible_causes` / `how_to_fix` 的 LLM 友好错误

---

## 测试组织

- **`test/`**（30 个文件）：主测试集，按子系统组织（建模/序列化/图/QL/装配/标准件/翻译器/工具链/验证器/错误）。`test_freecad_translator.py` 最大，但 FreeCAD 缺失时 `skipTest` 优雅跳过。
- **`tests/`**（2 个文件）：隔离测试（验证 core 不依赖 cadquery、拓扑身份）。

## 当前状态：2.0 重构进行中

`docs/core/rearchitecture_2_0.md` 显示重构仍在推进，关键 TODO：

- **TODO-KERNEL-001**：OCP-native evaluator 迁移
- **TODO-HIST-002**：shell 操作的 TopoDelta
- **TODO-FRAME-001/002**：显式坐标系抽象（`frame.py` 已引入但未完全集成）

---

## 一句话总结

> SimpleCADAPI 是一个为 AI agent 设计的、基于 OpenCascade 的函数式 CAD 建模 SDK。它通过"无侵入双写"架构，让用户在调用普通建模函数的同时自动生成可序列化、可重放的操作 DAG（含子形状级拓扑血缘），并以 model.json 作为 interchange 边界，支持 replay 和翻译到 FreeCAD。核心几何能力（含 STEP 导出）完全由 OCP 提供，FreeCAD 仅是可选的 .FCStd 导出后端。
