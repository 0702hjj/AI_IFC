# Script-as-source 统一编辑（web 修改 = 改脚本）设计

> 日期：2026-08-08 · 状态：待评审
> 前置：M5 script-as-source 转向（spec: 2026-08-06-script-as-source-design.md）、L1 属性真改直通（W-0019）
> 背景讨论：`~/Documents/md/dxf_agent/Revit.md`（Revit 式 IFC 编辑四层模型）

## 1. 决策摘要

**web 端的"修改"统一为"修改构建脚本"，IFC 永远是脚本的派生产物。**

- 有 AI 参与：必须 script-as-source。上传 IFC 的意图是**参考生成**——AI 经 MCP 读取上传 IFC，用 aiifc skill 复现出构建脚本，此后一切修改落在脚本上。
- 无 AI 的纯前端修改：同样走脚本路线（选中构件 → 定位脚本 → UI 改写）。
- **L1 直改链路（pending→commit 真改 IFC）整体扬弃**，从 git 历史可回捞（回捞锚点见 §9）。
- IFC 版本 delta 压缩方案（大版本锚点 + 字典压缩增量链）**正式归档为"不需要"**：脚本是 KB 级文本，全量快照本就轻；IFC 侧由「只物化最新」策略解决（§5.5）。
- 「回溯链过长自动压实为大版本、中间记录全部丢失」的机制**已存在**：staging 环（`MAX_STEPS=10`，超窗丢最老；`save` 压实成大版本并清空缓冲）。本设计直接沿用，不新建。
- 版本 diff 全面复用 M5 已建的 script diff（text + PARAMS 键级，大/小版本两级）。

### 被否方案记录

| 方案 | 否决理由 |
|---|---|
| IFC 版本存储重构（zstd 字典压缩增量链 + 压实策略） | script-as-source 下 IFC 快照是可再生缓存，优化对象不存在；过早优化 |
| 语义逆操作 undo 栈 | 删除/几何变更逆操作需完整捕获实体子图，不可靠 |
| 双轨（按模型类型分流：script-backed 改脚本 / 纯上传 IFC 保留直改） | 用户裁决：先试全量脚本化单轨，走不通再从 git log 回捞直改链路 |
| script-backed 模型上允许直改 + stale 标记 | 引入分叉状态，正是本轮要消除的债 |
| 内嵌 git（dulwich/pygit2）作为脚本版本存储 | 平台版本模型是「大版本检查点 + staging 环」，不需要分支/合并语义（v1 范围外的多用户领域）；git 表达不了三件成对 lockstep 约束；运行时依赖膨胀 |
| edit-service 重写为 Go/Rust/TS | 脚本运行时由契约锁定为 Python（aiifc 构建脚本 = ifcopenshell.api 代码）；可迁移的只是编排壳，而 diff 依赖 ifcdiff（Python）；性能瓶颈在 ifcopenshell C++ 内核而非 FastAPI；Go agent 框架（Eino，W-0017）经 REST 调用，进程边界即语言边界——既有 polyglot 设计不是债 |

## 2. 核心不变量（设计意图的确定性表达）

对应 blog 两条原则——状态机先行、类型系统承载语义：

- **I1（唯一事实源）**：对 script-backed 模型，IFC 文件 = `build(PARAMS)` 的纯函数输出。任何持久化的修改必然伴随一次脚本变更；不存在"IFC 变了脚本没变"的状态。
- **I2（可定位性）**：脚本创建的每个构件，其 `designKey → 源码调用点（行/列）` 映射在每次 save/run 时确定性地重新生成（运行期捕获），与版本 lockstep 存储。定位能力由**脚本契约条款**保证，不靠实现技巧。
- **I3（改写可验证）**：任何 UI 发起的脚本改写必须过沙箱重跑验证，build 失败 = 422 零副作用（沿用现有 staging 模式）。
- **I4（append-only 版本）**：回滚 = 恢复历史脚本重跑（git revert 语义），不改写历史；两个大版本之间不做逐步回溯（沿用 M5 裁决）。
- **I5（IFC 可重建）**：确定性 build（uuid5 GlobalId）保证同一脚本重跑产物语义稳定，因此历史版本的 IFC 是**可再生缓存**而非必须持久化的状态——只物化最新大版本，历史按需重建（§5.5）。

## 3. 状态机

```
                ┌─────────────────────────────────────────────┐
                │                                             │
 上传 IFC ──► plain ──(AI 经 MCP 读取 + skill 复现脚本)──► script-backed
                │                                             │
                │（直改链路扬弃后，plain 态不再有编辑入口）      │
                ▼                                             ▼
           仅查看/参考生成                          选中构件(guid)
                                                            │
                                              locate：查 v{n}.map.json
                                                            │
                                              ┌──── miss ───┴──── hit ────┐
                                              ▼                           ▼
                                      降级：只读提示              改写（二选一）
                                      （契约违规，               A. PARAMS 键 → 改值
                                       上报为 bug）              B. 内联值 → libcst 重写
                                                                          │
                                                              沙箱重跑验证（I3）
                                                                          │
                                                          ┌── 失败(422) ──┴── 成功 ──┐
                                                          ▼                          ▼
                                                     零副作用返回                staging 一步
                                                                                     │
                                                                              save → 大版本 v{n+1}
                                                                              (脚本+IFC+map 三件成对)
```

## 4. 设计意图的代码表达

对应 blog 两条原则，这一节是本设计的"语义锚点"——实现细节可迭代，本节的类型与转移规则是契约，改动必须回到本文档修订。

### 4.1 状态机即设计

主链路：`选中(guid) → 定位(map 查询) → 改写(libcst) → 沙箱验证 → staging → save`。每个转移有明确事件、守卫与失败分支，**失败分支与成功分支同为设计的一部分**：

| 当前态 | 事件 | 守卫 | 成功转移 | 失败分支 |
|---|---|---|---|---|
| 已选中构件 | locate | model 为 script-backed | → 已定位 | plain 态 → 无编辑入口（I1）；map miss → 200 `{found:false}` 降级只读提示（契约违规记 bug，不 5xx） |
| 已定位 | 改写 | origin=params → 路径 A；origin=literal → 路径 B；参数为标量字面量（C-scalar） | → 待验证 | 非标量/表达式注入 → 422，降级为脚本编辑器手改 |
| 待验证 | 沙箱重跑 | build(PARAMS') 可执行 | → staging 一步 | build 失败 → 422 零副作用（I3，沿用 staging 模式） |
| staging | save | 无 | → 大版本 v{n+1}（脚本+IFC+map 三件成对） | 写盘失败 → 原子写回滚，staging 保留 |
| 任意大版本 | rollback | 目标版本存在 | → 恢复脚本重跑（revert 语义，I4） | 版本不存在 → 404 |

### 4.2 类型即契约

- **`ScriptMap`**：`dict[DesignKey, CallSite]`，`CallSite.origin` 是和类型标签 `Literal["literal","params","traced"]`——UI 的改写策略（表单改值 / libcst 重写 / 只读）由 origin 分支决定，非法分支在类型检查期就不可能。
- **lockstep 编号**：`v{n}.py` / `v{n}.ifc` / `v{n}.map.json` 三件成对由 `script_versions.save` 的单一 max-n 规则保证，"stale map"在类型层面不存在（map 没有独立版本号可过期）。
- **契约条款即编译器可读的语义**：C-locate / C-scalar 写进 aiifc skill 契约并由打包器校验（tests/skill 断言条款存在），AI 生成脚本时违规 = skill 测试红，而不是线上才发现。

## 5. 组件设计

### 5.1 ScriptMap（定位链路，本迭代核心新增）

- **生成**：沙箱执行 `build()` 时，脚本契约的构件工厂入口记录调用点——`inspect.currentframe()` 取 `(filename, lineno, col)`，与 `designKey` 一起落 `{data_dir}/models/{id}/scripts/v{n}.map.json`。
- **存储**：`v{n}.map.json` 与 `v{n}.py` / `v{n}.ifc` 三件成对、lockstep 编号（沿用 script_versions.save 的 max-n 规则）。staging 步生成临时 map（内存或 staging 目录），不落版本。
- **类型**：

```python
class CallSite(TypedDict):
    line: int
    col: int
    snippet: str          # 调用行文本，UI 高亮用
    origin: Literal["literal", "params", "traced"]  # key 来源，供 UI 决定改写策略

ScriptMap = dict[str, CallSite]  # designKey → CallSite
```

- **失效语义**：map 与脚本严格同版本，不存在"stale map"状态——脚本一变（staging/save）map 即重生成。这把"map 是否过期"从运行期问题变成类型上不可能。

### 5.2 locate 端点

`GET /api/v1/models/{id}/script/locate?guid={globalId}`：

1. guid → designKey：读当前 IFC 的 `Pset_AIIFC.designKey`（确定性身份链已有）。
2. designKey → CallSite：查当前（staging 优先，否则最新大版本）map。
3. miss → 200 `{found: false}`（契约违规属 bug，但 API 不 5xx）。

### 5.3 UI 改写（两条子路径）

- **A. PARAMS 改写**：CallSite.origin == "params" 时，反查该构件绑定的 PARAMS 键（map 生成时一并记录 `params_keys: list[str]`），前端 PARAMS 表单（已有）定位到具体键改值 → 走现有 `PUT /script` 暂存。
- **B. 内联改写**：origin == "literal" 时，用 **libcst**（无损 CST，保留格式与注释）对调用点做参数级重写。
- **traced 降级**：origin == "traced"（key 运行期算出，非字面量/PARAMS）时 locate 仍可用（定位到工厂调用行），但 edit-call 拒绝自动改写，UI 引导至脚本编辑器手改该行——和类型三分支各有确定策略。新端点：

```
POST /api/v1/models/{id}/script/edit-call
{ "designKey": "...", "argument": "height", "value": 3.2 }
→ libcst 定位重写 → 沙箱验证 → 成功：等同一次 PUT /script 暂存；失败：422 + 错误定位
```

- 安全边界：edit-call 只允许替换**标量字面量参数**（str/int/float/bool），拒绝表达式注入——可编辑集合由 schema 显式枚举，而非"任意 Python"。

### 5.4 IFC → 脚本引导（bootstrap）

AI 路线（有 AI 的唯一入口）：

1. 用户上传 IFC（plain 态，仅可查看）。
2. AI 经 MCP server 读取模型（现有 mcp-server 已能解析 IFC）。
3. AI 用 aiifc skill 编写复现脚本 → 走现有 `PUT /script` + `script/run` 沙箱验证 → `script/save` 存大版本 v1，模型转为 script-backed。
4. 质量校验（防止"复现走样"）：save 后自动跑 IfcDiff（上传原件 vs 生成 v1）输出对齐报告（构件数、类型分布、pset 覆盖率），作为 bootstrap 的验收信号展示给用户。

前端路线（无 AI）：L2 的「选中 → 定位 → 表单改」建立在 script-backed 之上；plain 态模型前端不提供编辑入口（直改扬弃后的自然结果——无 AI 用户的小改发生在自己的 BIM/CAD 软件里，重新上传即新的参考输入）。

### 5.5 存储与保留策略

- **脚本**：全量大版本保留（KB 级，diff 的产品价值所在）。
- **map**：随脚本全量保留（KB 级）。
- **IFC**：只物化最新大版本；历史版本 IFC 在 diff/下载请求时从脚本**按需重建**（沙箱重跑）+ 结果缓存（容量上限 LRU 淘汰）。存量 `versions/v{n}.ifc` 迁移期保留，新模型不再逐版本落盘。
- **staging**：`MAX_STEPS=10` 环 + save 压实清空（现状沿用）。
- **PG**：`changes` / `overrides` 表随直改退役萎缩（新数据不再写入，历史只读）；`issues`（BCF 协同）保留。

### 5.6 大/小版本：语义分层，而非存储分层

脚本全量快照（KB 级）使大小版本在**存储与 diff 实现上完全统一**：同一个 `script_diff.diff_scripts(a, b)`（difflib 全文 diff + PARAMS 键级），无链式重建、无压缩、无两级引擎。剩余区别是纯语义/生命周期的：

| | 大版本 | 小版本（staging 步） |
|---|---|---|
| 语义 | 设计师认可的检查点 | 草稿步（"我刚改了什么"的即时确认） |
| 生命周期 | append-only、可 rollback、进版本列表 | 10 步环窗、save 压实丢弃 |
| diff 场景 | 版本间审查（脚本 diff + IFC 语义 diff/3D 着色，后者按需重建） | 相邻步 diff |

## 6. API 变更清单

| 端点 | 变更 |
|---|---|
| `GET /models/{id}/script/locate?guid=` | 新增 |
| `POST /models/{id}/script/edit-call` | 新增（libcst 标量重写 + 沙箱验证 + 暂存） |
| `GET /models/{id}/scripts` | 响应增 `hasMap` 字段 |
| bootstrap 对齐报告 | `POST /models/{id}/script/save` 响应可选携带 `alignment`（diff 摘要） |
| 直改链路端点（`PUT/DELETE /models/{id}/edit/entities/...`、`POST .../edit/commit` 等） | **退役**（见 §9 扬弃策略） |
| `POST /models/{id}/diff`（IFC 语义 diff） | 保留：大版本间 IFC diff 仍是 Diff Viewer 数据源 |

envelope `{code,message,data}` 与契约测试按 AGENTS.md 硬规则执行；改 API 后 `npm run gen:api && npm run check:api`。

## 7. 脚本契约新增条款（aiifc skill）

在现有契约（PARAMS 顶层字面量、uuid5 确定性 GlobalId、build() 入口）上追加：

- **C-locate**：构件必须经契约提供的工厂函数创建（工厂内部记录调用点）；禁止绕过工厂直接 `ifcopenshell.api.run("root.create_entity")` 创建审查可见构件。
- **C-scalar**：需要 web 端可编辑的参数必须是标量字面量或 PARAMS 引用，不得是任意表达式（否则 edit-call 拒绝，降级为脚本编辑器手改）。
- skill 的 references/templates 同步更新，打包器校验条款存在性。

## 8. 测试策略

- **ScriptMap**：save 后 map 与脚本/IFC 编号 lockstep；每个 designKey 有 CallSite；重跑同脚本 map 字节一致（确定性测试）。
- **locate**：guid→行号端到端（fixture 脚本已知行号断言）；miss 路径；staging 优先于大版本。
- **edit-call**：标量重写后 build 产物 diff 仅含目标属性变更；非法参数类型/表达式注入 → 422 零副作用；格式保留（注释、空行不动）。
- **bootstrap 对齐**：fixture IFC → 复现脚本 → alignment 报告字段完整性。
- **IFC 按需重建**：历史版本 diff 触发重跑重建 + 缓存命中；重建产物与（迁移期保留的）原快照语义 diff 为空（I5 的确定性验证）。
- **直改退役**：退役端点返回 410 Gone（语义明确的永久退役，不用 404）的契约测试（先写失败测试，按 AGENTS.md 纪律）。
- 测试量 ≥ 实现量（≥1:1），沙箱/状态机路径加码。

## 9. L1 直改链路扬弃策略

- **回捞锚点**：`fb55a8a`（2026-08-08 main HEAD，本 spec 分支点）。相关代码：`viewer/edit-service/app/routes_edits.py`、`pending.py`、`history.py`、web 端 PropertyPanel 真改表单、server 端 edit 代理与编排。
- **退役顺序**（独立工作项，先落后做）：① 契约测试固定退役行为 → ② 前端隐藏直改入口 → ③ edit-service 端点下线 → ④ server 代理清理 → ⑤ 文档站 editing.md 重写。
- **回捞判据**：bootstrap 复现质量不达标（对齐报告持续大面积 diff）或 edit-call 覆盖率不足以支撑设计师日常修改时，从 git log 恢复双轨。

## 10. 文档更新清单

- `docs/site/reference/design-edit.md`：改写为统一编辑模型（locate + edit-call + bootstrap）。
- `docs/site/viewer/editing.md`：L1 直改内容下线，改为脚本编辑流。
- `docs/site/viewer/versions-diff.md`：版本语义更新（脚本三件成对，IFC 快照为缓存）。
- `docs/site/project/roadmap.md`：已完成区补记；后续区移除"几何 diff"中已被本设计覆盖的表述。
- `README.md` / `README.zh-CN.md`：Key Advantages 表与 AI 路线表同步。
- AGENTS.md：组件表与 API 契约节在实现落地后同步。

## 11. 风险与开放问题

1. **bootstrap 复现质量**：任意上传 IFC 的脚本复现是 AI 能力问题，不是平台问题；对齐报告是兜底信号。这是单轨赌注的最大风险，回捞预案见 §9。
2. **trace 开销**：`inspect` 调用点记录对千级构件模型的 run 耗时影响需实测；预算 < 5% run 时间，超预算则改为契约工厂内显式传入 `__line__` 式编译期记录。
3. **map 与 staging 交互**：staging 撤销/重做时 map 同步重建，避免"撤销后定位到未来行"。
4. **多构件同 key**：契约已保证 key 唯一（uuid5 派生），定位天然一对一；重复 key 视为契约违规。
