# SimpleCADAPI skill 设计解剖 — AI_IFC skill 复刻蓝本

- 日期:2026-07-23
- 研究对象:`SimpleCADAPI/skills/simplecadapi/`(207 个文件:1 个 SKILL.md + 4 个顶层 references md + 201 个分页文档)
- 目的:回答"它如何把 STEP 建模知识拆成功能模块、又如何串联成 AI 可操作的体系",作为 `AI_IFC/skills/ai_ifc/` 的结构蓝本

---

## 1. 思维导图:知识模块全景

```text
simplecadapi skill
│
├── SKILL.md ........................ 入口:行为宪法 + 阅读地图(129 行)
│   ├── Philosophy(薄文档 skill,不打包源码)
│   ├── Working From Repo Root(路径约定)
│   ├── MUST Requirements ×17(硬性纪律)
│   ├── Standard Parts Library(标准件优先原则)
│   ├── Boolean result discipline(布尔纪律)
│   ├── Modeling Mental Model(建模心智模型)
│   ├── Tagging Mental Model(标签心智模型)
│   ├── SDK Focus(各 references 的分工指引)
│   └── Example SDK usage(最小可运行样例)
│
└── references/
    ├── SDK_PACKAGE_SUMMARY.md ...... L1 一页名片(21 行:是什么/入口列表)
    ├── SDK_OVERVIEW.md ............. L1 包地图(33 行:包含什么/不包含什么/表面清单)
    ├── SDK_SURFACES.md ............. L1.5 公共表面速览(75 行:六大 API 组 + 推荐阅读顺序)
    ├── MODELING_WORKFLOWS.md ....... L2 工作流模式(105 行:7 个编号场景,每景一段代码)
    │
    └── docs/
        ├── api/ 167 页 ............ L3 逐函数文档 + README 索引(按 15 个功能组分类)
        ├── stdlib/ 12 页 ........... L3 标准件工厂 + README 索引(按零件族分类)
        ├── core/ 17 页 ............. L3 核心类型语义(Vertex→Edge→Wire→Face→Solid→Compound)
        │   └── serialization/ ...... L4 序列化专题(4 页)
        └── architecture/ 1 页 ...... L4 架构评审
```

## 2. STEP 创建被拆成了哪些功能模块

api/README.md 把 167 个 API 按**动词语义**切成 15 组(每组即一个功能模块):

| 功能组 | 代表 API | 在 STEP 创建流水线中的角色 |
|---|---|---|
| Basic Creation(43) | `make_box_rsolid` / `make_circle_rface` / `make_polyline_rwire` / `make_segment_redge` | 图元生成(点/线/弧/面/体) |
| Transforms(3) | `translate/rotate/mirror_shape` | 位姿变换 |
| 3D Operations(4) | `extrude/loft/revolve/sweep_rsolid` | 低维→高维成形特征 |
| Advanced Features(4) | `fillet/chamfer/shell/helical_sweep_rsolid` | 细节特征 |
| Boolean Operations(3) | `union/cut/intersect_rsolid` | 体素合并/开洞 |
| Tagging and Selection(4) | `apply_tag/list_tags/select_*_by_tag` | 语义锚点 |
| Export(2) | `export_step` / `export_stl` | **输出边界(只有这里碰 STEP)** |
| Modeling Graph and Replay(10) | `GraphSession` / `export_model_json` / `replay_model_json` | 可回放记录 |
| Expressions and Parameters(6) | `Var` / `Const` / `Expr` | 参数化 |
| Sketch 约束(24) | `constrain_*_rsketch` | 2D 草图约束求解 |
| Assembly/Connector(15+) | `make_assembly_rassembly` / `add_*_constraint_rassembly` | 产品装配语义 |
| QL(submodule,8) | `ql.faces()/ql.tag()/ql.select()` | 接地查询语言 |
| Evolve(3) | `make_naca_propeller_blade_rsolid` 等 | 高阶派生件 |
| Math Helpers(2) | B 样条拟合 | 数学工具 |
| Types and Errors(6) | `SimpleCADError` / `Sketch*` | 类型与错误 |

**关键观察:STEP 并没有被"按 STEP 拆",而是按"建模动作"拆**。STEP 只是 Export 组里的一个函数;skill 教的是"建几何 → 打语义 → 输出"的通用流水线,导出格式是流水线的最后一步。AI_IFC 对应:`export_ifc` 也只是一个边界函数,主体模块应是"空间结构/元素/表示/材质/属性集"。

## 3. 知识是怎么串联的(AI 的学习路径设计)

这是 skill 设计最精华的部分 —— **一张"渐进展开 + 交叉引用"的网**:

### 3.1 纵向:四层渐进展开(progressive disclosure)

```text
L0 SKILL.md(129 行,常驻上下文)
  │ "MUST 1: 选 API 前先读 api/README 和 stdlib/README"
  ▼
L1 api/README + stdlib/README(索引,按功能分组)
  │ "MUST 2: 用到的每个 API 读它的专属 md 页"
  ▼
L2 SDK_SURFACES / MODELING_WORKFLOWS(模式与组合套路)
  │ "MUST 3: 涉及 Edge/Face/Solid/GraphSession 时读 core/ 对应页"
  ▼
L3 docs/api/<name>.md(单函数精确签名)/ docs/core/<type>.md
```

SKILL.md 本身不教 API,它教的是**"什么时候去读哪份文档"** —— 阅读顺序被写进 MUST Requirements 和 SDK_SURFACES 的 "Recommended reading order" 两处,互为印证。

### 3.2 横向:同一主题多视角重复(冗余即串联)

同一知识点在 3~4 个地方以不同粒度重复出现:

| 知识点 | SKILL.md | SDK_SURFACES | MODELING_WORKFLOWS | api/ 分页 |
|---|---|---|---|---|
| 关键词参数 | MUST 6 | — | — | 每页签名即关键词 |
| 逐步接地 print | MUST 10/11 | — | §5 QL-grounded workflow | — |
| 布尔返回单 Solid | MUST 12~16 + 专节 | — | §7 Boolean discipline | union_rsolid.md |
| 标准件优先 | MUST 4 + 专节 | 专节 | §4 | stdlib/ 12 页 |
| 可回放 JSON | MUST 7/17 | Typical surface | §1~3 | serializer 10 页 |

AI 无论从哪个入口切入,都会撞上同一套纪律 —— **用冗余对抗"只读了一份文档"的风险**。

### 3.3 命名即文档(词汇表纪律)

- 函数名自带返回类型后缀:`*_rsolid / *_rface / *_rwire / *_rassembly / *_rsketch`,AI 看名字就知道返回什么、能接什么
- API 分组标题本身就是建模流水线的阶段词:Creation → Transforms → 3D Operations → Boolean → Export
- 每个分页有 `Import Surface` 段,明确 top-level / submodule / translator backend 三种导入方式,杜绝 import 幻觉

### 3.4 心智模型章节:教"怎么想"而不只"怎么调"

SKILL.md 的 Modeling/Tagging Mental Model 两节是纯方法论:
- "低维到高维"(Vertex→Edge→Wire→Face→Solid)的构造顺序
- "函数式建模":操作返回新值,不改旧值
- "tag 存语义、metadata 存数值"的职责切分
- "QL 只打印当前步需要的事实"的接地方式

## 4. 单页文档的格式约定(可机器生成)

以 `extrude_rsolid.md`(17 行)为模板:

```markdown
# <api_name>
## API Definition
```python
def extrude_rsolid(profile: Union[Wire, Face], direction: Tuple[...], distance: ScalarLike) -> Solid
```
*Source: operations.py*
## Import Surface
- top-level: `from simplecadapi import extrude_rsolid`
## Description
一句话描述
```

极简、无示例、无散文 —— **它是"查签名"的字典,不是教程**。教程职责全部上移到 MODELING_WORKFLOWS。这与 agent 定义里"用 ifcedit/discover.py 从源码批量生成,不要手写"的要求完全同构:ifcopenshell 侧生成 `<module>.<function>.md` 时应采用同样的 4 段式(签名/来源/导入路径/一句话描述)。

## 5. 对 AI_IFC/skills/ai_ifc 的复刻清单

| SimpleCADAPI 做法 | AI_IFC 对应 |
|---|---|
| SKILL.md:Philosophy + MUST×17 + 两个 Mental Model + 最小样例 | 同款骨架;MUST 换成 IFC 纪律(关键词参数、每步 ifcquery 接地、Body 上下文复用、类型先行、层厚自校验、validate 终验) |
| api/README 按动词分 15 组索引 | api/README 按 IFC 领域分组:项目骨架(root/unit/context/spatial/aggregate)/ 表示(geometry)/ 洞口(feature)/ 类型(type)/ 材质(material)/ 属性(pset)/ 校验(validate) |
| 命名后缀 `_rsolid` 词表 | ifcopenshell 无此约定 → 在文档头建立"usecase 命名 = 动词_名词"词表,并给出返回实体类型 |
| 167 页 4 段式函数文档 | 用 `ifcedit/discover.py` 批量生成,保持 4 段式(签名/Source/Import Surface/Description) |
| MODELING_WORKFLOWS 7 个编号场景 | 按官方 geometry_creation 教程改写:从零骨架 → 墙 → 板/梁柱 → 洞口门窗 → 类型与材质集 → 校验导出,每景一段可运行代码 + 接地 print |
| core/ 类型语义页(Vertex→Solid) | core/ 放 IFC 概念页:ObjectPlacement(4x4 矩阵)/ RepresentationContext / Type 与 MappedRepresentation / MaterialLayerSet vs ProfileSet |
| stdlib/(标准件优先) | 对应"类型库/profile 库优先":参数化截面(HEA100 等)优先于任意轮廓 |
| QL 接地(ql.faces()...) | ifcquery(summary/tree/select/validate)+ selector 语法,写进 MUST |
| GraphSession/model JSON 回放 | 不对应(IFC 本身即 interchange),可省略;但保留"export_ifc 是唯一输出边界"纪律 |

## 6. 结论

SimpleCADAPI skill 的清晰来自四件事:

1. **按动作拆模块**(动词分组),输出格式(STEP)退化为一个边界函数
2. **SKILL.md 是宪法不是教程**:行为纪律 + 阅读地图,知识下沉到 references
3. **四层渐进展开 + 多视角冗余**:每份文档职责单一,靠 MUST 条款互相串联
4. **单页文档机器可生成**(4 段式),与 ifcedit/discover.py 批量生成路线天然契合

---

## 7. 追加调研:参考输入机制与文件边界(2026-07-23,源码实证)

问题:SimpleCADAPI 的"用户参考输入"如何传入?能否参考 DXF 平面图生成?能否载入既有 STEP 在局部区域修改?

### 7.1 参考输入的传入:两条通道

**运行时通道(对象即引用)** — `Solid/Face/Edge` 是 OCP 形状的薄包装(`.wrapped`),三种传入姿势:

- **参数直传**:`extrude_rsolid(profile=<Face>, direction=(0,0,1), distance=4.0)`;数值位为 `ScalarLike = float | Expr`,`Var(name, default)` 参数引用可直接传
- **上下文栈传入**:坐标基准不逐函数传,`with SimpleWorkplane(origin, normal):` 压栈,函数内部经 `get_current_cs()` 读取(core.py 栈式实现,退出自动弹栈)
- **QL 选择器传入**:`ql.faces().where(...).exactly(1).resolve(body)[0]` 选出的子形状直接喂下游特征

**序列化通道(引用可回放)** — 图记录时运行时引用自动转为 `GeometryRef(geo_selector 指纹 + source_node_id)`,指纹含 bbox/hash/几何类型,回放与 FreeCAD 翻译时能重新解析同一子形状;配套 `SemanticRef`/`SketchRef`。

参考结构全清单:`CoordinateSystem` / `SimpleWorkplane` / `Placement`(基准)、`Var`/`Const`/`Expr`/`ExpressionGraph`(数值引用)、`Sketch`+24 个 `constrain_*_rsketch`+`SketchRef`(2D 轮廓引用)、QL selector/`GeometryRef`(子形状引用)、`Connector`/`ConnectorAnchor`/`ConnectorRef`(装配基准,geometry/placement/forwarded 三形态)、tag/metadata(软锚点)。
边界:开发计划明确**不做通用 part reference API**,参考口子收敛为显式 connector/datum 接口。

### 7.2 DXF 参考:SDK 边界外(有意分层)

源码 grep 零 DXF 命中 —— SDK 不做任何文件解析。流水线分工:

```
DXF 文件 → [ezdxf / cad-to-shapely] → shapely 多边形(坐标)
        → SimpleCAD: make_polyline_rwire → make_face_from_wires_rface → extrude_rsolid
```

example 24 的 DXF 也是 ezdxf 生成的。**所有外部参考先归一化为 Python 对象再进 API**。

### 7.3 载入 STEP 局部修改:公共 API 不支持,底层有口子

- 全包仅 `export_step/export_stl`,无 `import_step`/`STEPControl_Reader` —— **构造式(authoring)SDK,非编辑式**
- 口子:`Solid(solid)` 构造器接受任意 OCP `TopoDS_Solid`(`as_solid()` 校验包装)→ 可用 OCP 原生 reader 读 STEP → 手工包装 → 照常布尔/特征 → 导出;代价是外来体无图记录来源,回放链断裂
- "局部区域修改"无现成原语,等效三件套:QL 按 `geo`/`value` 谓词(中心坐标/bbox)圈区域 → `SimpleWorkplane` 架局部系 → 布尔/特征修改;无盒选 API(对照 ifcopenshell `tree.select_box`)

### 7.4 设计结论与对 AI_IFC 的差异点

SimpleCAD 一句话:**文件格式归一化在 SDK 外,SDK 内只认 Python 对象引用;引用的可回放性由 GeometryRef 指纹保证**。

IFC 侧天生"读改一体"(`ifcopenshell.open()` → selector 过滤 → 修改 → validate → write 同库完成),ai_ifc skill **可原生支持**"载入既有 IFC → 按 storey/location/selector 圈定局部 → 修改 → 重新校验"工作流,应写成 skill 独立章节 —— 这是 SimpleCAD 走不通、IFC 独有的优势路径。
