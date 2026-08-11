# 05 参考库调查：不从零造轮子

> 2026-08-06。动机：求解器与周边算法应最大化复用前人成果。本文按 v2 架构的
> 四个算法需求层逐一调查候选库（GitHub 实测活跃度+许可证），给出采用结论。
> 结论先行：**求解层用 OR-Tools CP-SAT（含内置 AddNoOverlap2D);
> 矢量化用 shapely;打包类库不匹配我们的问题，只作启发参考；
> 设计模板种子首选 ZInD(Apache-2.0),CubiCasa5K 受 NC 限制仅作内部参考。**

## 1. 逐层调查

### 1.1 求解层（房间分配/布局约束）

| 库 | 实测（2026-08) | 许可证 | 匹配度 | 结论 |
|---|---|---|---|---|
| **google/or-tools** (CP-SAT) | 13.8k★，日活提交 | Apache-2.0 | 栅格 Bool 分配是 CP-SAT 原生问题；**内置 `AddNoOverlap2D`** 连续二维不重叠约束——正是路线 B（连续矩形精修）的现成引擎，不用自己实现矩形对偶 | **采用**。另：其 examples 与 MiniZinc 基准集含 VLSI floorplanning 模型，建模范式可直接借鉴 |
| secnot/rectpack | 561★,2021 停更 | Apache-2.0 | **不匹配**：它解"固定矩形装进箱子"(2D bin packing)，我们的房间形状是求解输出而非输入 | 不采用；其 skyline/maxrects 启发式作纯 Python 备选路线的参考读物 |
| 精确覆盖/DLX(polyomino tiling) | 多个小型实现 | 各异 | 房间=多连方块枚举+精确覆盖非重叠，是一条真实备选范式 | 记为备选；房间形状枚举爆炸风险高，不首选 |
| MiniZinc(建模范式) | 175★(IDE) | — | 不引入工具链，但其 floorplanning 模型文件是 CP 建模的教材 | 作参考阅读 |

**关键纠正**：调查前把"连续矩形化"（路线 B）标为"实现复杂度高一个量级"——
`AddNoOverlap2D` 的存在使该判断降级：连续阶段作为栅格解的精修后处理时，
可直接复用内置约束，复杂度高估了。

### 1.2 矢量化层（栅格分配 → 房间多边形/墙段）

| 库 | 实测 | 许可证 | 结论 |
|---|---|---|---|
| **shapely** | 4.5k★，日活 | BSD-3 | **采用**。单元并集（`unary_union`)→ 房间直角多边形；两房间多边形求交（`intersection`)→ 共享墙段；`buffer/offset` → 墙厚展开。全是几行调用的事 |
| opencv(findContours) | 5.3k★(python 绑定) | Apache-2.0 | 备选。像素轮廓追踪会引入光栅误差，栅格并集用 shapely 是**精确**运算，首选 shapely |
| potrace | — | GPL | 曲线描摹，与直角多边形需求错位，不用 |

另注：workspace 已有 `resource/cad-to-shapely`，收编评估时一并看。

### 1.3 生成式设计范式参考（不直接采用，借模式）

| 项目 | 情况 | 借鉴点 |
|---|---|---|
| hellguz/Magnetizing_FloorPlanGenerator | C#/Grasshopper,71★ | 力导向（"磁化"）布局范式——路线 C 的活例，我们已弃路线 C，仅存档 |
| hypar-io/Elements | C#,408★，日活，含 DXF/IFC 序列化 | 建筑构件库架构参考；语言不同不引入。其"函数化生成建筑"的产品形态值得对照 |
| Autodesk Forma / TestFit | 闭源 | 输入参数形态参考（已在 plan_format_research §3.2) |

### 1.4 设计模板种子库（02 篇的"精品模板"来源）

v1 三金样是回归资产不是设计模板（用户已指出）。外部真实设计数据集：

| 数据集 | 实测 | 许可证 | 结论 |
|---|---|---|---|
| **zillow/zind**(Zillow Indoor Dataset) | 256★ | **Apache-2.0** | **首选种子**。真实住宅户型+房间类型标注；Apache-2.0 无传染性，衍生模板可自由用 |
| CubiCasa/CubiCasa5k | 558★,5000 套芬兰户型矢量标注（SVG+房间类型） | **CC BY-NC 4.0(非商业)** | ⚠️ **受限**：只可作内部研究参考，衍生模板不可随开源项目分发、不可商用。可作"反编译管线"的开发样本，不入正式模板库 |
| RPLAN | Google 表单申请制 | 未公开 | 暂不申请；ZInD 够用 |
| Structured3D | 需签协议 | 受限 | 暂不碰 |

种子管线：ZInD/CubiCasa 矢量标注 → `layout.from_dxf` 同族的 `layout.from_zind`
解析器 → 气泡图 JSON → **人工精选**（好设计才入库，量不在多，02 篇已定性）。

## 2. 采用清单（更新 architecture.md §6-1 的拍板建议）

```jsonc
// skills/aidxfv2/scripts/packages/layout 的依赖
"ortools": "CP-SAT 求解内核",        // Apache-2.0
"shapely": "栅格矢量化/墙段求交",     // BSD-3
// 不引入:rectpack / opencv / potrace / minizinc / hypar
```

- 两个依赖均为纯 Python wheel、宽松许可证、日活维护——风险最低组合。
- 栅格分配（主求解）+ AddNoOverlap2D（连续精修，后补）同库覆盖，无第二求解器。

## 2b. 实际落位清单（2026-08-06 已下载安装）

运行时环境：`skills/aidxfv2/.venv`(requirements.txt 已同步 5 项）;
源码参考统一放 `src/`（不入构建，供阅读/查文档）。

| 库 | 版本 | 构建作用（在 v2 管线的哪个环节干什么） | 落位 |
|---|---|---|---|
| **ortools** | 9.15.6755 | **求解层**:CP-SAT 把"每格归哪个房间"建成布尔约束方程组求解（面积区间/连通/共享边界/预锁定/目标权重）;`AddNoOverlap2D` 留作二期连续矩形精修引擎 | .venv + `src/or-tools/`(161M，含 CP 建模 examples) |
| **shapely** | 2.1.2 | **矢量化层**：格子集 `unary_union` → 房间直角多边形；两多边形 `intersection` → 共享墙段；面积实算/贴外轮廓判定/墙厚 offset | .venv + `src/shapely/`(3.3M) |
| **ezdxf** | 1.4.4 | **画法与反编译**:archdxf 的底座（DXF 读写）;P1 `layout.from_dxf` 从 v1 金样语义实体反解气泡图 | .venv(v1 既有依赖） |
| **jsonschema** | 4.26.0 | **契约校验**:S0 用 plan/cad_draft 两份 JSON Schema 做确定性校验，防模型"目测通过" | .venv |
| **pytest** | 9.1.1 | **TDD**：全部任务的反例先行测试框架 | .venv |
| numpy | 2.5.1（传递依赖） | 栅格数组运算（CP-SAT 建模式标配） | 随 ortools 自动带入 |

数据资产：

| 项 | 落位 | 说明 |
|---|---|---|
| **ZInD**(zillow/zind,Apache-2.0) | `resource/zind/`(160M，含 sample_tour) | 设计模板种子源。已验证格式：每层每房间 vertices（米制）+ windows + doors 显式标注，够反编译 door/front_door 边;**缺口：无房间类型标签**，精选入库时人工标注。全量数据用其 download_data.py 拉取（需 requests/tqdm，开发期 sample_tour 够用） |

不引入的候选（rectpack/opencv/potrace/hypar/Magnetizing/MiniZinc)：仅存档
为范式参考，未下载。

## 3. 对既有文档的修订点

1. `architecture.md` §6-1:OR-Tools 依赖问题 → **建议拍板接受**（本调查支撑）。
2. `01_layout_solver.md` §1 路线 B 评价：复杂度判断需按 AddNoOverlap2D 下调，
   路线 B 从"后补"提为"二期精修模块"。
3. `02_template_retrieval.md` §6.1：模板种子来源明确为 ZInD 解析 + 人工精选；
   CubiCasa5K 标注 NC 警告。
4. `buildV2/README.md` 设计立场补一条：**算法复用优先于自研，引入依赖需过
   许可证（宽松/无传染）与活跃度（近一年有提交）双门。**
