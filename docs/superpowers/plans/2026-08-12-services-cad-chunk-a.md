# services/cad 地基（Chunk A：cad_script_lib + 服务骨架）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 spec `2026-08-12-services-cad-script-as-source-design.md` 的工作项 1-2：交付 `cad_script_lib`（XDATA 确定性身份 + 契约校验）与 `services/cad` 服务骨架（staging/versions/run/save/rollback + 沙箱 + REST）。

**Architecture:** 镜像 services/ifc 的 script-as-source 全套：脚本唯一事实源（`scripts/v{n}.py`）+ 派生物 DXF（`versions/v{n}.dxf`）+ ScriptMap 侧车（XDATA key → callsite）。实体身份 = XDATA（APPID `AIDXF`，1000 组码存 key 字符串 `{layer}:{kind}:{n}`）。ezdxf 为唯一 DXF 依赖（PyPI/uv 管理）。

**Tech Stack:** Python 3.10 + FastAPI + ezdxf（PyPI）+ libcst（edit-call 留 chunk B，本 chunk 不引）+ uv；测试 pytest + stdlib unittest（tests/skill）。

## Global Constraints

- **自包含硬规则**：禁止引用仓外路径（`../ezdxf`、`../libredwg` 仅作只读调研参考，不进代码/文档/依赖）；ezdxf 走 uv 依赖（`ezdxf>=1.3`，与 mcp/pyproject.toml 既有口径一致）。
- 迭代分支 `feat/v0.5-portability-reuse` 继续累积；commit 中文前缀式。
- 测试纪律：先失败测试后实现；新增测试量 ≥ 新增实现量。
- 校验隔离：业务校验住 `verify*`/`validate*`，handler 只做 decode→verify→调领域→翻译错误；配 test_verify_isolation 同款契约测试（ALLOWLIST 重造）。
- MIT 边界：`skills/aidxfv/v1` 是 MIT fork——新增文件（flows/cad_script_lib.py 等）在文件头注 AGPL 还是 MIT？裁决：**主仓新增文件标 AGPL-3.0-only**，不改既有 MIT 文件的许可头；SKILL.md 增补节以「主仓追加」口吻写，不动原 fork 文本归属。
- spec 分期决策（本计划裁决）：`script/save` 响应的 bootstrap 对齐 diff **计数**依赖语义 diff 引擎（工作项 3，chunk B），本 chunk save 只落 bootstrap.dxf 保留与成对快照，响应不含 alignment 字段——chunk B 补齐，届时改响应需配契约测试。
- chunk A 不含：locate/edit-call、实体级语义 diff、routes_user_edits、Go 网关接入、Dockerfile（随 chunk C 网关接入时补）、services/cad openapi 导出。
- services/cad 无鉴权，只绑 127.0.0.1（文档注明）。

---

### Task 1: 立项 W-0032/W-0033 + PLAN v0.6 行

**Files:**
- Create: `docs/work/items/W-0032-cad-script-lib.md`
- Create: `docs/work/items/W-0033-services-cad-skeleton.md`
- Modify: `docs/work/PLAN-v0.1.0.md`

- [ ] **Step 1: 两个 item 文件**（模板照 docs/work/README.md，风格照 W-0026）

- W-0032「cad_script_lib + 契约校验」：P1，Milestone v0.6，来源 spec §1.1/测试要求。验收：`validate_script_contract` 正反例测试、XDATA key 确定性测试（同脚本两跑 key 全同）、`add_entity` 七类实体工厂、write_and_validate 落裸 map、aidxfv v1 SKILL.md 契约节 + registry/打包测试绿。
- W-0033「services/cad 骨架」：P1，Milestone v0.6，来源 spec §1.2。验收：staging/run/save/rollback/scripts/params/script-diff/versions-list 端点齐 + 沙箱（bwrap/rlimit/killpg/原子发布）+ verify 隔离契约测试 + `uv run --group dev pytest` 全绿；明示不含 locate/edit-call/语义 diff（chunk B）。

- [ ] **Step 2: PLAN 加 v0.6 行**

```markdown
| v0.6 | services/cad script-as-source（spec: 2026-08-12-services-cad-script-as-source-design.md，分支 feat/v0.5-portability-reuse 累积）| W-0032, W-0033（chunk A）| cad_script_lib 契约+XDATA 身份测试绿；services/cad 骨架端点与沙箱全测试绿 |
```

- [ ] **Step 3: Commit** `docs(work): W-0032/W-0033 立项 + PLAN v0.6 行`

---

### Task 2: cad_script_lib（TDD）+ aidxfv skill 契约节

认领 W-0032（in-progress）。

**Files:**
- Create: `skills/aidxfv/v1/scripts/flows/__init__.py`（空文件）
- Create: `skills/aidxfv/v1/scripts/flows/cad_script_lib.py`
- Test: `tests/skill/test_cad_script_lib.py`
- Modify: `skills/aidxfv/v1/SKILL.md`（增补契约节）
- Modify: `tools/skill_pack.py`（aidxfv1 registry 加 `scripts/flows/cad_script_lib.py`）
- Modify: `tests/skill/test_skill_pack.py`（如 registry 断言需同步）

**Interfaces（Produces——后续 Task 与 chunk B 依赖这些名字）:**

```python
# cad_script_lib.py 公共面
APPID = "AIDXF"
def reset_state() -> None            # 清 _CALLSITES 与 key 计数器（沙箱/测试每次跑前调）
def add_entity(msp, kind: str, layer: str = "0", key: str | None = None, **kwargs):  # → ezdxf entity
def get_entity_key(entity) -> str | None
def write_and_validate(doc, out_path) -> bool   # saveas + audit + 写裸 map 侧车
def validate_script_contract(path) -> list[str] # 空列表=通过
```

- [ ] **Step 1: 写失败测试 `tests/skill/test_cad_script_lib.py`**

接入模式照 `tests/skill/test_script_contract.py:9-18`：`sys.path.insert(0, str(REPO_ROOT/"skills/aidxfv/v1/scripts/flows"))` + `pytest.importorskip("ezdxf")`。每个测试 setUp 调 `cad_script_lib.reset_state()`。

覆盖（每条的断言要点）：

```python
class TestContract:  # validate_script_contract 正反例（tmp_path 写脚本字符串）
    - 好脚本（PARAMS 字面量 + build(params, out_path) + __main__ 守卫）→ []
    - 缺 PARAMS / PARAMS 非字面量 dict / PARAMS 非 JSON-compatible（含 set）/ 缺 build / build 参数不足 / 缺 __main__ → 错误列表非空且含对应中文子串
class TestIdentity:  # XDATA key
    - add_entity 自动分配 key 形如 "{layer}:{kind}:{n}"（n 从 1 起，同 layer:kind 递增）
    - 同脚本两跑（两个新 doc 各跑一遍同一 build 函数体）key 序列全同（确定性）
    - 显式 key= 参数优先于自动分配
    - get_entity_key 读回 == 写入值；无 XDATA 实体返回 None
    - doc.appids 含 "AIDXF"（写盘前已注册）
class TestEntities:  # 七类工厂（LINE/CIRCLE/ARC/LWPOLYLINE(含 bulge)/TEXT/MTEXT/INSERT）
    - 每类：add_entity 后实体 dxftype 正确、XDATA key 在、几何参数落地（如 CIRCLE 半径）
class TestWriteAndValidate:
    - write_and_validate 产出 out.dxf 可读回（ezdxf.readfile）+ audit 无不可恢复错 → True
    - 裸 map 侧车 `out.dxf.map.json` 写出：dict，每个 key 有 line/col/snippet/origin/params_keys 五字段
    - PARAMS 引用的实体 origin=="params" 且 params_keys 含引用首键；字面量 origin=="literal"（复刻 IFC _classify_origin 语义）
class TestDocDrift:  # 照 TestSkillDocContractDrift：SKILL.md 中所有 cad_script_lib.<name> 引用 hasattr 存在
```

- [ ] **Step 2: 跑确认失败** `.ci-venv/bin/python -m pytest tests/skill/test_cad_script_lib.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现 `cad_script_lib.py`**

文件头：`# SPDX-License-Identifier: AGPL-3.0-only`（主仓新增文件）。实现要点：

```python
NAMESPACE_AIDXF = uuid.UUID("8f2e1c4a-3b5d-4e6f-9a0b-1c2d3e4f5a6b")  # 固定常量
_CALLSITES: OrderedDict[str, dict] = OrderedDict()
_KEY_COUNTERS: dict[tuple[str, str], int] = {}

_KIND_DEFAULTS = {...}  # kind → (msp 方法名, 必填 kwarg 校验)
```

- `add_entity(msp, kind, layer="0", key=None, **kwargs)`：kind 大写分派——LINE(start,end)/CIRCLE(center,radius)/ARC(center,radius,start_angle,end_angle)/LWPOLYLINE(points,closed=False)/TEXT(text,insert,height=2.5)/MTEXT(text,insert)/INSERT(name,insert)；未知 kind → ValueError 中文报错。layer 经 dxfattribs 传入。key 为 None 时 `_KEY_COUNTERS` 递增分配 `{layer}:{kind_lower}:{n}`（kind 小写入 key，与 IFC `{storey}:{kind}:{n}` 风格一致）。注册 APPID（`if APPID not in msp.doc.appids: msp.doc.appids.add(APPID)`）后 `entity.set_xdata(APPID, [(1000, key)])`。callsite 记录：`_classify_origin`/`_params_ref_keys`/`_record_callsite` 三个 helper 从 `skills/aiifc/references/docs/flows/script_lib.py:49-142` 复刻（逐行搬，改注释口径为 DXF）。
- `get_entity_key(entity)`：`entity.has_xdata(APPID)` → `entity.get_xdata(APPID)` 取首个 (1000, ...) 值；异常/缺失 → None。
- `write_and_validate(doc, out_path)`：`doc.saveas(out_path)` → `auditor = doc.audit()` → 裸 `_CALLSITES` dict 写 `str(out_path)+".map.json"`（indent=2，与 IFC 侧裸 map 同形——信封由 services/cad 沙箱包装）→ `return not auditor.has_errors()`。
- `validate_script_contract(path)`：照 script_lib.py:232-284 复刻四项检查（可解析/PARAMS 字面量 JSON-compatible/build ≥2 位置参数/__main__ 守卫），返回中文错误字符串列表。
- `reset_state()`：清两个全局。

- [ ] **Step 4: SKILL.md 增补节 + registry**

`skills/aidxfv/v1/SKILL.md` 末尾追加（主仓追加节，不动原文）：

```markdown
## services/cad 脚本契约（build 形，主仓追加）

面向 services/cad script-as-source 管线的 DXF 构建脚本采用与 aiifc 同形的契约（区别于 cadpy CLI 的 `gen_dxf()` 契约）：
顶层 `PARAMS` 字面量 dict、`build(params, out_path)` 入口、`__main__` 守卫、实体一律经 `cad_script_lib.add_entity` 工厂（XDATA 确定性身份）、出口 `cad_script_lib.write_and_validate`、增量编辑不重写。实现与校验：`scripts/flows/cad_script_lib.py`（`validate_script_contract` 为唯一校验点）。
```

`tools/skill_pack.py` 的 `aidxfv1` registry 元组加 `"scripts/flows/cad_script_lib.py"`。

- [ ] **Step 5: 全量测试绿** `.ci-venv/bin/python -m pytest tests/skill/ -q` → 全 PASS

- [ ] **Step 6: W-0032 置 done + Commit**

`feat(skills): cad_script_lib——XDATA 确定性身份 + add_entity 工厂 + build 形契约校验（W-0032）`

---

### Task 3: services/cad 地基（非沙箱部分 + 测试）

认领 W-0033（in-progress）。

**Files（全部 Create，镜像 services/ifc 对应文件后按清单改）:**
- `services/cad/pyproject.toml`（deps: fastapi/uvicorn[standard]/ezdxf>=1.3/python-multipart；dev: pytest/httpx；`[tool.uv] package=false`；pytest pythonpath=["."]）
- `services/cad/.python-version`（3.10）
- `services/cad/app/__init__.py`、`config.py`、`main.py`、`route_common.py`、`script_staging.py`、`script_versions.py`、`versions.py`、`script_params.py`、`script_diff.py`
- `services/cad/tests/conftest.py` + 测试文件（下述）

**Interfaces:**
- Consumes: `cad_script_lib.validate_script_contract`（Task 2，经 `AIDXF_FLOWS_DIR` 定位——本 Task 只经 config 传递路径，执行在 Task 4）
- Produces: `create_app()`；`Settings(port=8200, data_dir, flows_dir, max_models)`；env：`CAD_SERVICE_PORT`/`VIEWER_DATA_DIR`/`AIDXF_FLOWS_DIR`（默认 `../../skills/aidxfv/v1/scripts/flows`）；数据布局 `models/{id}/scripts|versions|script_staging.json` + `uploads/{id}.dxf`

- [ ] **Step 1: 拷后改清单（逐文件执行）**

1. `config.py`：env 名三换（EDIT_SERVICE_PORT→CAD_SERVICE_PORT 默认 8200；AIIFC_FLOWS_DIR→AIDXF_FLOWS_DIR；VIEWER_DATA_DIR 不变）；`flows_dir` 默认 `../../skills/aidxfv/v1/scripts/flows`；删掉 `diff_timeout_s`（chunk B 再加）。
2. `main.py`：只挂 scripts router + `/health`；`app.state` 挂 `settings` + `script_staging = StagingRegistry(settings.data_dir)`；**不要** ModelRegistry/PendingStore（chunk A 无实体缓存与 L1 遗产）。
3. `route_common.py`：`MODEL_ID_PATTERN` 保留（同 `^m_[0-9a-f]{16}$`）；`model_upload_path` → `uploads/{id}.dxf`；`model_lock`：因无 registry，改为模块级 `dict[str, threading.RLock]` + 守卫锁按 model_id 发放（单点定义在此，禁止复制第二份）。
4. `script_staging.py`：原样镜像（纯文本暂存，无 ifc 依赖）。
5. `script_versions.py` + `versions.py`：`VERSION_FILE_RE` 与快照扩展名 `.ifc`→`.dxf`；`_prune_rebuildable_snapshots` 保留（versions 只留最新物化）；**删** `ifc_materialize.py` 引用——历史 DXF 按需重建属 chunk B（本 chunk versions 列表只列已物化 + scripts）。
6. `script_params.py` / `script_diff.py`：原样镜像（纯 ast/文本，无 ifc 依赖）。
7. `pyproject.toml` 按上表写；`uv lock` 生成锁文件。

- [ ] **Step 2: conftest 与首批测试（TDD：先写后实现路由）**

`services/cad/tests/conftest.py`（镜像 ifc conftest 三 fixture）：

```python
MODEL_ID = "m_0123456789abcdef"
# dxf_path fixture: ezdxf.new("R2010") 建一个 LINE+CIRCLE（经 cad_script_lib.add_entity 写 XDATA），存 tmp
# data_dir fixture: tmp/models + uploads/{MODEL_ID}.dxf（拷 fixture）
# client fixture: monkeypatch VIEWER_DATA_DIR + TestClient(create_app())
```

测试文件与覆盖（镜像 ifc 侧同名测试语义）：
- `test_script_staging.py`（环形暂存全语义，可直接镜像改造）
- `test_script_params.py`（PARAMS ast 提取/替换）
- `test_script_diff.py`（脚本文本 diff + params_changes）
- `test_script_versions.py`（大版本锁步/裁剪）
- `test_health.py`

- [ ] **Step 3: 跑确认失败** → 实现 → 转绿

```bash
cd services/cad && uv run --group dev pytest
```

- [ ] **Step 4: Commit** `feat(services/cad): 地基——config/main/staging/versions/params/script_diff 镜像 ifc（W-0033 上半）`

---

### Task 4: services/cad 沙箱 + 路由（TDD）

**Files:**
- Create: `services/cad/app/script_runner.py`、`routes_scripts.py`
- Test: `services/cad/tests/test_script_runner.py`、`test_routes_scripts.py`（端点面）、`test_bootstrap_alignment.py`（bootstrap.dxf 保留，不含 diff 计数）、`test_state_persistence.py`、`test_verify_isolation.py`

**Interfaces:**
- Consumes: Task 2 `cad_script_lib`（`AIDXF_FLOWS_DIR` 注入沙箱 PYTHONPATH）；Task 3 全部模块
- Produces（chunk B 依赖）: 端点形状与 IFC 完全一致：`GET/PUT /models/{id}/script`、`GET .../script/params`、`POST .../script/undo|redo|discard`、`POST .../script/run`、`POST .../script/save`、`GET .../scripts`、`POST .../script/rollback`、`POST .../script/diff`、`GET .../script/staging/diff`、`GET .../versions`；map 信封 `{"scriptHash": sha256(script), "map": {...}}` 发布到 `models/{id}/current.map.json`

- [ ] **Step 1: 先写 test_verify_isolation.py 与 test_script_runner.py（失败先行）**

- `test_verify_isolation.py`：镜像 services/ifc 同款（ast 扫 routes_*.py，`raise HTTPException` 只准在 verify*/validate* 或 route_common.py），ALLOWLIST 清空重建 + 自证用例。
- `test_script_runner.py`（镜像 ifc 16 用例语义）：契约门 422（坏脚本不进沙箱）、超时 killpg（死循环脚本→422 超时）、非零 exit stderr 截尾 2KB、无产出 422、map 信封发布（scriptHash 正确）、rlimit 降级路径（bwrap 缺失时 monkeypatch detect_backend）。

- [ ] **Step 2: 实现 script_runner.py（拷后改）**

镜像 services/ifc `script_runner.py`，改：tmp 前缀 `aiifc-run-*`→`aidxf-run-*`；产出物 `out.dxf`；`_load_script_lib`→`_load_cad_script_lib`（import `cad_script_lib`，先调 `reset_state()` 再执行用户脚本——沙箱内 runner 脚本模板里调）；`_sandbox_env` PYTHONPATH=flows_dir；map 信封同形（`script_hash` + 原子发布 + 无 sidecar 删旧）。沙箱内执行模板：把用户脚本写 workdir/script.py，runner 先 `cad_script_lib.reset_state()` 再 runpy 执行，产出 `out.dxf` + `out.dxf.map.json`。

- [ ] **Step 3: 写路由测试（失败）→ 实现 routes_scripts.py → 转绿**

镜像 ifc `routes_scripts.py`，端点见 Produces 表。要点：
- verify 函数（`verify_script_body`/`verify_params_target`/`verify_script_contract`）单点在本文件，错误翻译 422/409 与 ifc 同语义。
- `PUT /script` 首次暂存 `_preserve_bootstrap`：`uploads/{id}.dxf` 存在则拷 `models/{id}/bootstrap.dxf`。
- `run`：沙箱跑 staging 脚本 → 原子覆盖 `uploads/{id}.dxf` + 发布 `current.map.json`；不落版本。所有 mutating 端点持 `model_lock(model_id)`。
- `save`：run 后 `script_versions.save` 成对快照 + staging.save()；响应**不含** alignment 字段（Global Constraints 分期决策）。
- `rollback`：恢复大版本脚本进 staging 并重跑。
- `GET /versions`：列 scripts + 已物化 versions。
- `test_bootstrap_alignment.py`：只断言 bootstrap.dxf 首暂存保留、save 后仍在。
- `test_state_persistence.py`：staging 重启恢复。

- [ ] **Step 4: 全量绿 + 测试量对账**

`uv run --group dev pytest`（services/cad 目录）；新增测试数 ≥ 新增实现规模的 1:1（报告里给出两端计数）。

- [ ] **Step 5: W-0033 置 done + Commit** `feat(services/cad): 沙箱 + script-as-source 路由全套（W-0033 下半）`

---

### Task 5: 收口（README/AGENTS/PLAN）

**Files:**
- Create: `services/cad/README.md`（启动：`VIEWER_DATA_DIR=... uv run uvicorn app.main:app --port 8200`；与 ifc 的关系；无鉴权只绑 127.0.0.1；chunk 边界说明）
- Modify: `AGENTS.md`（组件表加 services/cad 行：目录/测试命令/启动；「项目是什么」逻辑二状态改为「services/cad 骨架已交付（chunk A），diff/编辑 API 与前端待续」；测试计数不动 web/server）
- Modify: `docs/work/PLAN-v0.1.0.md`（v0.6 chunk A 行勾掉 ✅）
- Modify: `docs/work/items/W-0030-services-cad-direction.md`（补一行：chunk A 已落地，剩余见 spec 工作项 3-7 后续 chunk）

- [ ] **Step 1-3: 写/改/验证**（`cd services/cad && uv run --group dev pytest` 复跑确认；`cd docs && npm run docs:build` 不涉及可不跑——本 task 不动 site）
- [ ] **Step 4: Commit** `docs: services/cad chunk A 收口——README + AGENTS 组件表 + PLAN v0.6 勾选`

---

## Self-Review 记录

- Spec 覆盖：工作项 1→Task 2；工作项 2→Task 3/4；测试要求的契约/沙箱/确定性条款→Task 2/4 测试清单；工作项 3-7 显式出 chunk（PLAN 行注明）。
- 占位符：镜像类文件给「拷后改清单」而非全文（源文件在仓内可读，逐字重印 500 行无价值）；新逻辑（cad_script_lib API、conftest、registry 键）给了真实代码/签名。
- 类型一致：`AIDXF_FLOWS_DIR`/`CAD_SERVICE_PORT`/`create_app()`/`reset_state()` 在 Task 2-4 间一致；map 信封与 IFC 同形（chunk B locate 依赖 scriptHash）。
- 风险：rlimit 沙箱在本机/CI 的 bwrap 有无 → 测试需 monkeypatch 覆盖两条路径；ezdxf 版本 ≥1.3 的 audit API 稳定（mcp 已依赖同线）。
