# AI BIM 总体架构（当前版，2026-07-30）

> 本文是 deep-research-report（`~/Documents/md/dxf_agent/deep-research-report.md`，下称「报告」）愿景的**当前落地形态**。
> 报告是愿景层，本文是实现层；逐条目标↔实现映射见 `research/overview.md`，迭代计划见 `docs/work/PLAN-v0.1.0.md`。

## 一、定位

AI_IFC 是一个**自托管、开源的 IFC 审查与编辑平台**。报告的完整愿景包含三条主线：IFC 的版本追踪（§1）、人/AI 双角色编辑 API（§2）、IFC→Python 生成管线（§3）。当前版本（v1 方向）的取舍：

- **我们做**：IFC 显示 + 人的修改闭环 + 版本追踪/存储 + 供 AI 接入的编辑架构（报告 §1、§2.1/§2.2/§2.4、§4.2 主体）
- **另一同学做**：AI 生成本体、AI 沙箱（§2.3）、IFC→Python 工具（§3）——经我们交付的接口接入
- **明确不做（v1）**：鉴权/多用户、Git 存 IFC（§4 混合存储的 Git 半）、RAG

## 二、四条工作线

| 工作线 | 状态 | 说明 |
| --- | --- | --- |
| 1. AI 生成 IFC 的 skill | 另一同学负责 | 调研已备（`research/ifc/`）；接入走我们的双角色编辑 API，MCP 化 v1.1 候选 |
| 2. Viewer（审查+编辑平台） | **N+2 完成** | 本文档主体；五个组件端到端可用 |
| 3. 后端 DB 集成 | viewer 侧已落地 | issues/changes/overrides 三表 File/PG 双实现；gaia_* 平台侧未对接 |
| 4. 与 IfcOpenShell 的符合度 | 已决策 | 前端 web-ifc（展示），后端 IfcOpenShell（真改/diff）——见 §七偏差 1 |

## 三、总体架构

```mermaid
graph LR
  subgraph 客户端层
    UI[浏览器<br/>React 19 + xeokit<br/>viewer/web]
    AI[AI Agent<br/>（另一同学的生成线）]
  end

  subgraph 服务层
    GO[Go server :8090<br/>viewer/server<br/>编排 / REST / 存储抽象]
    PY[Python edit-service :8100<br/>viewer/edit-service<br/>FastAPI + IfcOpenShell]
    CV[Node converter<br/>viewer/converter<br/>IFC → XKT + metadata.json]
  end

  subgraph 存储层
    PG[(PostgreSQL<br/>issues / changes / overrides)]
    FS[(文件系统<br/>uploads/*.ifc, models/{id}/)]
  end

  UI -->|REST envelope| GO
  AI -->|同一套编辑 API，REST 直连| PY
  AI -->|或经 Go 代理| GO
  GO -->|/api/models/{id}/edit/* 代理 + 编排| PY
  GO -->|子进程 node convert.js| CV
  GO -->|pgx/v5，可选| PG
  GO --> FS
  PY -->|真改 IFC / 版本快照 / history| FS
  CV -->|model.xkt + metadata.json| FS
```

### 组件职责

| 组件 | 技术 | 职责 | 为什么是这个技术 |
| --- | --- | --- | --- |
| web | React 19 + TS + Vite + zustand + xeokit-sdk | 审查/编辑/Diff 的全部交互 | xeokit 的 XKT 二进制加载 + BIM 工具链（拾取/剖切/测量） |
| server | Go 1.26（stdlib net/http + pgx/v5 唯一三方依赖） | 上传/转换队列、REST、编辑编排、存储抽象（File/PG 双实现） | 静态编译、并发模型、与原有代码一致 |
| converter | Node CLI（web-ifc + xeokit-convert） | IFC→XKT 几何 + 语义提取（空间树/pset，GlobalId 为键） | xeokit-convert 只有 npm 形态 |
| edit-service | Python 3.10 + FastAPI + ifcopenshell + ifcdiff | 真改 IFC、pending/commit、版本快照、语义 diff | IfcOpenShell 是 IFC 编辑的事实标准（Python/C++） |
| PG | PostgreSQL（可选） | issues/changes/overrides 三表 | 不配置 `pgDSN` 时全部落文件，零依赖可跑 |

三语言并存是**生态现实**而非设计偏好：每个语言绑定的都是该生态里唯一或最优的 IFC 库。服务间通过 REST 与子进程解耦，任一组件可独立替换。

## 四、核心数据流

### 4.1 上传转换流（报告未含，我们先落地的底座）

```
浏览器上传 .ifc → Go 校验/存 uploads/{id}.ifc（status=converting）
  → 转换队列（2 worker，dedup + dirty 重跑）→ node convert.js
  → models/{id}/model.xkt（几何）+ metadata.json（空间树/pset，metaObject id = GlobalId）
  → status=ready → 前端 XKTLoaderPlugin 同时加载几何与语义
```

关键不变量：**XKT 构件 id = metadata metaObject id = IFC GlobalId**——选中、着色、diff 结果全靠这条链对齐。

### 4.2 编辑流（报告 §2.2 + §2.4 Figure 2）

```
PUT /models/{id}/entities/{guid}  {fields, psets, author, provenance}
  → 校验全部字段（任一不合法 → 422 零副作用）→ 应用到内存模型 → 记 pending（含从 IFC 读的真原值 oldValue）
  → 磁盘不变
POST /models/{id}/commit
  → 原子写盘（tmp+rename，持每模型锁）→ 版本快照 versions/v{n+1}.ifc → 追加 edit-history.json → 清 pending
（经 Go 代理时，编排继续：）
  → change log 按字段展开（operation=update，diff 由 IfcDiff v{n-1}→current 补充，非致命）
  → 转换队列重转 XKT → 前端轮询到 ready 自动重载
```

- pending 存内存，服务重启丢失（v1 文档化限制）；`DELETE /pending` 丢弃并回滚到磁盘状态
- 多请求并发由「每模型一把锁」串行化；重复 commit 返回 409
- **AI 直连注意**：直连 Python 的 commit 不经过 Go 编排（无 Go change log、无自动重转）；完整链路走 Go 代理。已在 `docs/site/reference/ai.md` 写明

### 4.3 版本与 diff 流（报告 §1.3）

- 首次 commit 前把原始上传复制为 `versions/v1.ifc`；每次 commit 快照 `v{n+1}.ifc`（只增不改）
- `POST /models/{id}/diff {base, target}`：
  - IfcDiff（`relationships=["attributes","property"]`，从构造上排除几何）给出 added/removed 集合与 changed-guid 门控
  - 适配层对门控实体用 `get_info()`+`get_psets()` 自算字段级 old/new（ifcdiff 的 change_register 只存布尔）
  - 归约为 `{added:[guid], removed:[guid], changed:[{guid, changes:[{field,old,new}]}]}`
  - 快照间 diff 结果缓存（版本不可变，缓存天然有效）
- Diff Viewer：added→绿、changed→黄（`entity.colorize`）；removed 在当前 XKT 已无几何，只进红色列表（设计决策）

### 4.4 override → 真改迁移流（报告 §2.2 的两阶段策略）

早期属性编辑走 override（不改 IFC 本体的显示层，白名单五字段）。`POST /api/models/{id}/overrides/migrate` 回放迁移：

```
读全部 override → 逐 entity 映射（Name/Description/Comments → fields；
  FireRating → 从 metadata.json 反查所在 pset；Classification → 试 fields，422 则进 failed）
→ 每 entity 一次 PUT（pending）→ 全部一次 commit（operation=migrate）
→ 成功字段清 override；change log 带真原值 oldValue；失败字段保留 override 并在响应 failed 中带原因
→ 有任何成功 → 重转
```

## 五、commit / 版本模型（报告 §1.1/§1.4 落地形态）

报告 schema → 当前实现：

| 报告字段 | 落地 |
| --- | --- |
| author | `change.Entry.Author`（默认 `local-user`，v1 无认证） |
| timestamp | `CreatedAt`（UTC） |
| operation | `update` / `migrate`（N+2 补齐，File/PG 双 store 归一化） |
| diff | `Entry.Diff`（jsonb/json，commit 时 IfcDiff 补充） |
| provenance | `{source: UI\|AI}`，API 层枚举校验 |
| parent / 版本链 | `versions/v{n}.ifc` 线性快照序列（分支/合并未做，属多用户 v2） |

存储分布（已知技术债，见 §八）：Go `change.Store`（File changes.json / PG changes 表）是 UI 面向的修改记录；edit-service `edit-history.json` 存真原值 oldValue 的编辑史；pending 在内存。三者粒度与用途不同，v2 考虑归并单源。

## 六、双角色 API 与 AI 接入（报告 §2.1/§2.3）

- **人**：浏览器 → Go 代理（`/api/models/{id}/edit/*`）→ edit-service；编排附带 change log + 重转
- **AI**：REST 直连 edit-service 或经 Go 代理，**同一套端点**；`provenance.source="AI"` 标记来源
- **工具目录**（报告 §2.3 的 REST 形态）：`docs/site/public/ai-tools.openapi.json`（FastAPI 导出，`viewer/edit-service/scripts/export_openapi.py` 再生成，保证文档与实现不漂移）+ `docs/site/reference/ai.md`（端点目录、JSON Schema、curl 全流程）
- **MCP**：报告 §4.1 建议 REST+MCP 双暴露；v1 REST 先行，MCP 薄包装（参考 ifcmcp 31 工具模式）列 v1.1
- **沙箱/代码执行**：属 AI 侧范围；架构不阻塞（edit-service 进程隔离，后续可加 execute 端点）
- **认证**：v1 单机自托管不做（报告 §2.1 的 OAuth2/RBAC 属 v2）；provenance 是声明字段，无防伪语义

## 七、与报告的偏差（决策记录）

1. **前端解析栈**：报告未指定；我们选 web-ifc + xeokit-convert（非 IfcOpenShell WASM，调研结论「启动重，不适合生产级前端」）。「同一套 ifcopenshell.api」的符合度由后端 edit-service 承担
2. **存储**：报告 §4 混合存储（Git+DB）——DB 半已落地（PG 三表 + File 降级），Git 半暂缓（SPF step-id 噪声问题无收益优先级）
3. **oldValue**：override 阶段记录前次 override 值（历史数据保留）；真改阶段起一律为 IFC 真原值（N+2 已解决）
4. **几何 diff**：报告 §1.3 全量 IfcDiff——v1 限定属性级（几何 diff 的计算量与语义噪声，见 [PLAN v0.1.0](../../work/PLAN-v0.1.0.md)）
5. **script-as-source（2026-08-06 用户裁决，M5 已落地）**：Python 构建脚本取代 design JSON 成为 IFC 的唯一一一对应表示。design JSON 降级为 AI 起草阶段的辅助草稿——不是完整表示、不是 IFC 标注文件、不进版本、不参与 diff。存量 design JSON 管线（regenerate / design 表单 / design 大版本与 diff 引擎）直接下线，老模型仅保留 IFC 快照。版本模型不变（大版本回退 + 5-10 步短回溯暂存链），diff 三层×两级（脚本 text/PARAMS diff + ifcdiff 属性级 + 外部模型兜底）。完整 spec：`docs/superpowers/specs/2026-08-06-script-as-source-design.md`

## 八、边界与技术债

**v1 明确不做**：鉴权/多用户、AI 生成本体、IFC→Python（§3）、Git 存 IFC、RAG、几何 diff、增量重转。

**已知技术债（按优先级）**：
1. 三份历史（Go change.Store / edit-history.json / 内存 pending）——已出现一次 operation 漂移（终审修复），v2 归并单源
2. ~~ifcdiff 本地 editable 依赖~~——**已解决（2026-08）**：`ifcopenshell`/`ifcdiff` 改为 PyPI 官方发布，`uv sync` 直接安装，无本地源码依赖（skill 侧 `ifcquery` 随 `skills/aiifc/requirements.txt` 提供）
3. pending 内存态（重启丢失）——v2 持久化
4. diff 无超时控制（大模型阻塞 threadpool）——N+3
5. Python 侧存储仅文件模式（PG 模式下 versions/history 仍在文件）——文档声明，v2 评估

## 九、路线

- **N+3（进行中规划）**：docker compose 一键起、README/文档（本文档即其一）、CI、LICENSE 审计、v0.1.0 发布——`docs/work/PLAN-v0.1.0.md`
- **v1.1 候选**：MCP 包装、几何 diff、增量重转、execute 沙箱端点（AI 侧）
- **v2**：多用户/鉴权/冲突合并（版本前置条件 + GlobalId 三方合并，快照与 diff 已备地基）、历史单源化、IFC→Python 管线
