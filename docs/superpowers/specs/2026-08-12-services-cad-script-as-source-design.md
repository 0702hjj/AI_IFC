# services/cad：DXF script-as-source 设计（前两块实现路径 + 后两块展望）

**日期：** 2026-08-12
**状态：** 已确认（用户裁决，2026-08-12 brainstorming 会话）
**前置：** `2026-08-11-platform-framework-design.md`（逻辑二与 ifc 同构）、`docs/work/items/W-0030-services-cad-direction.md`（方向锁定）、`docs/internal/architecture/ai-cad-v2-contract.md`（DXF web 编辑纪律 + 同步桥）、`2026-08-06-script-as-source-design.md`（IFC 侧范式）
**范围：** 四个问题中——①DXF 版本管理（script-as-source）与②前端显示给出实现路径；③前端编辑直达 script 层与④DWG/DXF 导入归一给大致展望，实施前各自补独立 spec。

## 决策（用户裁决）

1. **ezdxf 坐 ifcopenshell 位**：AI 生成 DXF 的 Python 脚本唯一调用 ezdxf；libredwg 只做导入边界的 DWG→DXF 转换器（converter 位），不进生成路径。理由：libredwg 是 C 库、Python 绑定实验性、写支持差；ezdxf 纯 Python、读写成熟，且已在 aidxfv/archdxf/cadpy/mcp 全线使用，生态零迁移成本。pivot 格式统一为 DXF，DWG 一律先转 DXF。
2. **稳定身份 = XDATA 确定性 key + ScriptMap 复刻**：DXF handle 由 CAD 软件分配、重存全变（`mcp/app/dxf_diff.py` 已踩坑），不能当 GlobalId 用。身份载体是工厂写入的 XDATA key（APPID `AIDXF`），key = `uuid5` 风格确定性派生（格式 `{layer}:{kind}:{n}`），并产出 ScriptMap 侧车（key → 脚本行号/列/参数键）。diff、locate、edit-call 全部建立在其上。
3. **前端显示 = entity-keyed JSON + Canvas 2D**：服务端 ezdxf 解析产出带稳定 key 的实体级 JSON（扩展现有 `skills/aidxfv/v1/scripts/dxf/render_payload.py` 的 schema 思路，但升级为实体带 key），前端 Canvas 2D 渲染。选中即得 key，为 Phase 2 编辑打通 locate/edit-call。不采 JS DXF 解析库（选中映射回稳定 key 困难），不采无身份 SVG path（现 render_payload 形态只能做只读缩略图）。
4. **两阶段实施**：Phase 1 服务端闭环（services/cad 全套 API + 只读 Canvas 预览）；Phase 2 前端编辑。先把 AI 闭环跑通。

## 一、实现路径：DXF 版本管理（script-as-source）

### 1.1 DXF 脚本契约（进 aidxfv skill MUST，复刻 aiifc #25–31）

1. 脚本头部 `PARAMS = {...}` 顶层字面量 dict（JSON-compatible），所有可调参数集中于此
2. 入口 `build(params: dict, out_path: str) -> None` + `__main__` 读 PARAMS 调 build
3. **确定性身份**：实体一律经 `cad_script_lib.add_entity(kind, **kwargs)` 工厂创建；工厂分配确定性 key（uuid5 风格），写 XDATA（APPID `AIDXF`），并记录 callsite
4. **C-locate**：只允许工厂创建实体，否则 web「选中→定位脚本」失效
5. **C-scalar**：web 可编辑参数必须是标量字面量或 PARAMS 引用（edit-call 改写的前提）
6. 退出走 `cad_script_lib.write_and_validate(doc, out_path)`：ezdxf audit/recover 校验 + 写 ScriptMap 侧车 `out.dxf.map.json`（`{key: {line, col, snippet, origin, params_keys}}`，envelope 带 `scriptHash`，与 IFC 侧 `script_runner.py:271` 同形）
7. **增量编辑不重写整个脚本**（script diff 是 AI 下次输出的上下文）

`cad_script_lib` 放置参照 IFC 侧分工：skill flows 目录为唯一实现，services/cad 经环境变量路径 import（同 `AIIFC_FLOWS_DIR` 机制），保证 skill 与 edit-service 共用一份契约校验 `validate_script_contract()`。

### 1.2 services/cad（FastAPI，建议 :8200，与 services/ifc :8100 同构）

- **文件布局**（`VIEWER_DATA_DIR/models/{id}/` 下，镜像 IFC 侧）：`scripts/v{n}.py` + `v{n}.meta.json` + `v{n}.map.json`（全留）、`versions/v{n}.dxf`（只留最新，旧的裁剪）、`script_staging.json`（WPS 式 10 步环形暂存）、`current.map.json`、`bootstrap.dxf`（导入原件，对齐 diff 基准）
- **成对快照**：`scripts/v{n}.py` 与 `versions/v{n}.dxf` 同 n lockstep；回退 = 恢复脚本进暂存 + 重跑，永不逐步 revert
- **沙箱**：复用 services/ifc `script_runner.py` 模式——静态契约门 → subprocess + 临时目录，bwrap 优先 / rlimit 兜底，killpg 超时，stderr 截尾 2KB → 422，tmp + `os.replace` 原子发布
- **REST 端点形状与 IFC 完全一致**：

| 端点 | 语义 |
|---|---|
| `GET/PUT /models/{id}/script` | 读当前脚本（暂存或基线）/ 暂存编辑（`{script}` 全量 xor `{params}` 服务端拼接 PARAMS 块） |
| `GET .../script/params` | ast 提取 PARAMS（不执行），喂前端表单 |
| `POST .../script/undo\|redo\|discard` | 暂存链导航 |
| `POST .../script/run` | 沙箱试跑 → 原子替换当前 DXF + 发布 map；预览，不成版本 |
| `POST .../script/save` | 跑 + 成对快照；失败 422 不留版本；响应带 bootstrap 对齐 diff 计数 |
| `GET .../scripts` · `POST .../script/rollback` | 大版本列表 / 回退 |
| `POST .../script/diff` · `GET .../script/staging/diff` | 大版本 diff（unified + params_changes）/ 暂存步间 diff |
| `GET .../script/locate?key=` | key → XDATA → map callsite；`scriptHash` 不匹配 → `{found:false, stale:true}` fail-closed |
| `POST .../script/edit-call` | libcst 标量改写；stale map 409；仅服务直连暴露，不经 Go 代理 |
| `GET .../versions` · `POST .../diff` | 版本列表 / 实体级语义 diff（不可变对缓存 `diff-{base}-{target}.json`） |

- **语义 diff**：推广 `mcp/app/dxf_diff.py`——对齐键从 DXF handle 迁移到 XDATA key；按实体类型比较属性集（LINE 端点、CIRCLE 圆心半径、LWPOLYLINE 顶点+bulge、TEXT/MTEXT 内容、INSERT 块名+变换、图层、线型、颜色）。**与 IFC 的本质差异：CAD 里几何就是数据，坐标参与 diff**（IFC 侧 v1 明确不 diff 几何）。输出 `{added, removed, changed:[{key, changes:[{field,old,new}]}]}`，同 IFC diff schema。
- **校验纪律**：遵守仓内硬规则——业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；`test_verify_isolation` 同款契约测试。

### 1.3 Go 网关与 MCP

- Go 代理镜像 `server/internal/api/script.go`：fast/slow 双 client（run/save/rollback 走 120s slow），成功后自动入队 DXF→render.json 重生成（对应 IFC 的 XKT reconvert）
- MCP 现有 `dxf_upload_modified` 工具切到新 diff 引擎（XDATA key 对齐），provenance=USER 标注不变

## 二、实现路径：前端显示

1. **render payload v2**（services/cad 侧，ezdxf 解析）：`GET /models/{id}/render.json` → `{schemaVersion:2, entities:[{key, type, layer, geometry...}], layers:[...], bounds}`；覆盖 LINE/LWPOLYLINE(含 bulge→arc)/CIRCLE/ARC/TEXT/MTEXT/INSERT 展开；不支持的实体列入 `unsupported:[{type, handle, coords}]` 明面化（ai-cad-v2-contract 纪律：不静默丢）
2. **web 新增 CAD 查看器组件**：Canvas 2D（自绘或 Konva，不引 WebGL——2D 图纸 YAGNI）；pan/zoom、图层开关、hover/选中显示 key + 属性面板；XKT viewer 与 CAD viewer 按模型类型路由（ViewerPage 分流）
3. **模型类型**：Go 侧 model 记录加 `kind: "ifc"|"dxf"`，上传/转换管线分流（DXF 无需 converter 子进程，services/cad 直接产 render.json）

## 三、展望：前端编辑直达 script 层（Phase 2，实施前补独立 spec）

- PARAMS 表单 + 脚本编辑器镜像 DesignPanel（dotted-path 扁平化、`origin` 分流聚焦）
- Canvas 拖拽端点/半径/移动 → 命中 key → locate → `edit-call` 标量改写（409 stale fail-closed），改写即沙箱试跑 + 暂存一步
- diff 着色按 key（added 绿 / changed 黄），对应 DiffPanel 的 ifc 着色页签
- 图层纪律遵循 ai-cad-v2-contract §3：非契约实体（手绘线等）报「无法解析实体 + 坐标」，不静默通过

## 四、展望：DWG/DXF 导入归一（唯一 script，实施前补独立 spec）

- **形态：逐实体转录**（用户裁决）。importer 把每个 DXF 实体确定性地转录为工厂调用：固定遍历序（layer → 实体类型 → 原 handle 排序），相同输入 → 相同脚本 = 唯一性；几何 100% 保真、可逆。无语义参数，后续由 AI/用户增量重构为语义化 script（增量不重写的契约纪律在此同样适用）
- **DWG 路径**：libredwg `dwg2dxf`（converter 位，Go 子进程调用）→ DXF → 同一转录器，之后只有 ezdxf 一条路径
- **对齐校验**：保存时 `bootstrap.dxf`（导入原件）vs 脚本重建 DXF 的语义 diff 应为零增删，计数随 save 响应返回（镜像 IFC 侧 alignment 机制）；用户外部改后上传经 MCP 标注 USER 来源
- **不转录即报错**：importer 白名单之外的实体类型直接报「无法解析实体 + 坐标」，不静默丢弃

## 测试要求（遵循仓内 ≥1:1 硬规则）

- 契约测试：`validate_script_contract()` 正反例；XDATA key 确定性（同脚本两跑 key 全同）
- 沙箱测试：超时 killpg、rlimit、原子发布（镜像 services/ifc 现有用例）
- diff golden：每类实体的 added/removed/changed 字段级用例
- 转录器 round-trip（展望项落地时）：导入 → 脚本 → 重建 → 语义 diff 为空
- render payload：实体 key 与 map 一致性契约测试

## 工作项建议

1. cad_script_lib + 契约校验（skill flows，契约测试先行）
2. services/cad 骨架：staging/versions/run/save/rollback + 沙箱（镜像 services/ifc，可拷后改）
3. 语义 diff 引擎（XDATA key 对齐，mcp dxf_diff 迁移）
4. locate/edit-call（libcst 改写 + stale fail-closed）
5. render payload v2 + Go `kind` 分流 + 重生成队列
6. web CAD Canvas 查看器（只读）+ 属性面板
7. Go 代理路由 + MCP diff 切换
8.（展望）导入转录器 spec → 实现
9.（展望）前端编辑 spec → 实现

依赖序：1 → 2 → 3 → 4 → 5 → 6 → 7；8、9 各自独立 spec 后排期。
