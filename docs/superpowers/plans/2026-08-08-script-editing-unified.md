# Script-as-source 统一编辑实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** web 修改统一为改构建脚本——ScriptMap 定位（选中构件→脚本调用点）、libcst 内联改写 + 沙箱验证、bootstrap 对齐报告、IFC 只物化最新、L1 直改链路退役。

**Architecture:** spec `docs/superpowers/specs/2026-08-08-script-editing-unified-design.md`（不变量 I1-I5、状态机、存储策略以此为准）。核心新增在 edit-service（script_lib 调用点捕获 + locate/edit-call 端点）与 aiifc skill 契约条款；前端只做 locate 跳转与直改入口隐藏。

**Tech Stack:** Python 3.10 / FastAPI / ifcopenshell / libcst（新增依赖）/ React 19 + zustand / Go 1.26。

## Global Constraints

- 测试纪律：先失败测试后实现；测试量 ≥ 实现量；测试与源码同目录（`test_*.py` / `*.test.ts(x)` / `*_test.go`）。
- commit 信息中文、前缀式；分支 `feat/script-editing-unified`（从 main 切出，不与 docs/script-editing-unified 混用）。
- API 变更走 envelope `{code,message,data}` + 契约测试；改端点后 `cd docs && npm run gen:api && npm run check:api`。
- modelId 格式 `^m_[0-9a-f]{16}$`；版本名 `^v\d+$`。
- edit-service 测试命令：`cd services/ifc && uv run --group dev pytest`；web：`cd web && npm test && npm run lint`；server：`cd server && go test ./...`；skill：`python -m pytest tests/skill/ -q`（CI 用独立 .ci-venv）。
- 沙箱相关测试结束必须等异步落地（条件轮询，禁止固定 sleep）。
- edit-call 只允许标量字面量（str/int/float/bool），拒绝表达式注入（spec §5.3 / C-scalar）。

---

## Phase 1 — 定位与改写内核

### Task 1: script_lib 调用点捕获（ScriptMap 生成）

**Files:**
- Modify: `skills/aiifc/references/docs/flows/script_lib.py`（create_entity 记录调用点；write_and_validate 落 map sidecar）
- Test: `services/ifc/tests/test_script_map_capture.py`（经 run_script 端到端验证）

**Interfaces:**
- Produces: 模块级 `_CALLSITES: dict[str, dict]`，条目结构 `{"line": int, "col": int, "snippet": str, "origin": "literal"|"params"|"traced"}`；`write_and_validate(model, out_path)` 额外写 `str(out_path) + ".map.json"`（Task 2 消费此文件）。

- [ ] **Step 1: 写失败测试**

`services/ifc/tests/test_script_map_capture.py`：

```python
"""ScriptMap capture: create_entity records callsites; write_and_validate dumps map."""

import json
import os

from app.config import Settings
from app.script_runner import run_script

SCRIPT = '''
import sys
from pathlib import Path
sys.path.insert(0, os.environ.get("PYTHONPATH", ""))
from script_lib import create_entity, create_skeleton, write_and_validate
import ifcopenshell

PARAMS = {"wall_name": "W1"}

def build(params, out_path):
    model = ifcopenshell.file(schema="IFC4")
    body, _ = create_skeleton(model)
    w = create_entity(model, "IfcWall", key="s1:wall:1", name=params["wall_name"])
    write_and_validate(model, out_path)

if __name__ == "__main__":
    import sys as _s
    build(PARAMS, _s.argv[1])
'''


def test_run_script_produces_map_sidecar(settings: Settings, tmp_path):
    out = str(tmp_path / "out.ifc")
    run_script(settings, SCRIPT, out)
    map_path = out + ".map.json"
    assert os.path.isfile(map_path)
    m = json.loads(open(map_path, encoding="utf-8").read())
    assert "s1:wall:1" in m
    entry = m["s1:wall:1"]
    assert entry["origin"] == "literal"
    assert entry["line"] > 0
    assert "create_entity" in entry["snippet"]
```

（`settings` fixture 见 conftest.py 现有写法；SCRIPT 中 `import os` 需补上。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd services/ifc && uv run --group dev pytest tests/test_script_map_capture.py -v`
Expected: FAIL（out.ifc.map.json 不存在）

- [ ] **Step 3: 实现**

`script_lib.py` 追加（import 处加 `import inspect, linecache`，`from collections import OrderedDict`）：

```python
_CALLSITES: "OrderedDict[str, dict]" = OrderedDict()


def _classify_origin(filename: str, lineno: int) -> str:
    """按调用行源码分类 key 参数来源：字面量 / params 引用 / 其他（traced）。

    多行调用等解析失败场景一律降级 "traced"（可定位、不可自动改写）。
    """
    line = linecache.getline(filename, lineno).strip()
    try:
        tree = ast.parse(line)
    except SyntaxError:
        return "traced"
    call = next((n for n in ast.walk(tree) if isinstance(n, ast.Call)), None)
    if call is None:
        return "traced"
    kw = next((k for k in call.keywords if k.arg == "key"), None)
    if kw is None:
        return "traced"
    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
        return "literal"
    if isinstance(kw.value, (ast.Subscript, ast.Attribute, ast.Name)):
        return "params"
    return "traced"


def _record_callsite(key: str) -> None:
    """记录 create_entity 调用点（用户脚本帧 = f_back.f_back）。"""
    frame = inspect.currentframe()
    try:
        caller = frame.f_back.f_back
        if caller is None or not key:
            return
        info = inspect.getframeinfo(caller, context=1)
        snippet = (info.code_context or [""])[0].strip()
        _CALLSITES[key] = {
            "line": info.lineno,
            "col": info.index or 0,
            "snippet": snippet,
            "origin": _classify_origin(caller.f_code.co_filename, info.lineno),
        }
    finally:
        del frame
```

`create_entity` 内 `attach` 前加 `_record_callsite(key)`；`write_and_validate` 末尾（validate 之后）加：

```python
    map_path = str(out_path) + ".map.json"
    Path(map_path).write_text(
        json.dumps(_CALLSITES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

- [ ] **Step 4: 补边界测试**——params 引用 key（`key=keys["w"]`）→ origin=="params"；多行调用 → origin=="traced"。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd services/ifc && uv run --group dev pytest tests/test_script_map_capture.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add skills/aiifc/references/docs/flows/script_lib.py services/ifc/tests/test_script_map_capture.py
git commit -m "feat(skill): script_lib 调用点捕获——create_entity 记录 CallSite，出口落 map sidecar"
```

---

### Task 2: map 发布与 lockstep 存储

**Files:**
- Modify: `services/ifc/app/script_runner.py:168-232`（run_script 增 `map_out` 参数）
- Modify: `services/ifc/app/script_versions.py:80-112`（save 增 `map_text` 参数）
- Modify: `services/ifc/app/routes_scripts.py`（_run_into_uploads 写 current.map.json；save_script 传 map）
- Test: `services/ifc/tests/test_script_map_storage.py`

**Interfaces:**
- Consumes: Task 1 的 `out.ifc.map.json` sidecar。
- Produces: `run_script(settings, script_text, out_path, *, map_out: str | None = None)`；`script_versions.save(data_dir, model_id, script_text, ifc_src_path, note="", map_text=None)`；`{data_dir}/models/{id}/current.map.json`（Task 3 消费）；`scripts/v{n}.map.json`。

- [ ] **Step 1: 写失败测试**

```python
"""Map publication: run writes current.map.json; save writes v{n}.map.json lockstep."""

import json

from app import script_versions


def test_save_writes_map_lockstep(client, data_dir, model_id):
    # PUT 脚本（含 create_entity 调用）→ save
    ...  # 复用 test_script_staging.py 的 _script fixture 模式
    r = client.post(f"/models/{model_id}/script/save", json={})
    version = r.json()["version"]
    map_file = data_dir / "models" / model_id / "scripts" / f"{version}.map.json"
    assert map_file.is_file()
    m = json.loads(map_file.read_text(encoding="utf-8"))
    assert m  # 至少一个 designKey
    # current.map.json 同步存在
    current = data_dir / "models" / model_id / "current.map.json"
    assert current.is_file()
```

- [ ] **Step 2: 跑测试确认失败**（map 文件不存在）

- [ ] **Step 3: 实现**

`script_runner.run_script` 签名加 `map_out: Optional[str] = None`，成功发布 out.ifc 后：

```python
        if map_out is not None:
            tmp_map = tmp_out + ".map.json"
            os.makedirs(os.path.dirname(map_out), exist_ok=True)
            if os.path.isfile(tmp_map):
                dest = map_out + ".tmp"
                shutil.copyfile(tmp_map, dest)
                os.replace(dest, map_out)
```

`script_versions.save` 加 `map_text: Optional[str] = None`，写完 meta 后：

```python
    if map_text is not None:
        _write_atomic(os.path.join(directory, f"{version}.map.json"), map_text)
```

`routes_scripts._run_into_uploads`：

```python
    map_out = os.path.join(
        request.app.state.settings.data_dir, "models", id, "current.map.json"
    )
    script_runner.run_script(request.app.state.settings, script, ifc_path, map_out=map_out)
```

`save_script` 在 `script_versions.save(...)` 调用前读 current.map.json（不存在则 None）传入 `map_text`。

- [ ] **Step 4: 跑测试确认通过 + 回归** `uv run --group dev pytest`（全量，确认 test_script_staging 等不破）

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(edit-service): ScriptMap 发布——current.map.json + v{n}.map.json lockstep"
```

---

### Task 3: locate 端点

**Files:**
- Modify: `services/ifc/app/routes_scripts.py`（新增 GET /models/{id}/script/locate）
- Test: `services/ifc/tests/test_script_locate.py`

**Interfaces:**
- Consumes: Task 2 的 current.map.json；`registry.load(path)`（registry.py:45）；`ifcopenshell.util.element.get_psets`。
- Produces: `GET /models/{id}/script/locate?guid=...` → `{"found": bool, "designKey"?: str, "line"?: int, "col"?: int, "snippet"?: str, "origin"?: str}`（Task 4 与前端消费）。

- [ ] **Step 1: 写失败测试**

```python
def test_locate_hit(client, data_dir, model_id):
    # PUT + save 一个含 create_entity(key="s1:wall:1") 的脚本（origin literal）
    ...
    # 从 uploads IFC 读该构件的 GlobalId（ifcopenshell.open + by_type("IfcWall")[0].GlobalId）
    r = client.get(f"/models/{model_id}/script/locate", params={"guid": guid})
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["designKey"] == "s1:wall:1"
    assert body["origin"] == "literal"
    assert body["line"] > 0


def test_locate_miss_unknown_guid(client, model_id):
    r = client.get(f"/models/{model_id}/script/locate", params={"guid": "0" * 22})
    assert r.status_code == 404  # guid 不在模型里


def test_locate_no_designkey_returns_not_found(client, model_id):
    # 模型里存在但无 Pset_AIIFC.designKey 的构件（如 IfcProject）
    ...
    assert r.json()["found"] is False
```

- [ ] **Step 2: 跑测试确认失败**（404 route）

- [ ] **Step 3: 实现**

routes_scripts.py 追加：

```python
@router.get("/models/{id}/script/locate")
def locate_callsite(
    request: Request, guid: str = Query(...), id: str = Path(pattern=MODEL_ID_PATTERN)
) -> Dict[str, Any]:
    """Locate the script callsite for an IFC element (guid → designKey → CallSite)."""
    ifc_path = _upload_path(request, id)
    model = request.app.state.registry.load(ifc_path)
    try:
        element = model.by_guid(guid)
    except RuntimeError:
        raise HTTPException(status_code=404, detail=f"element not found: {guid}")
    psets = ifcopenshell.util.element.get_psets(element)
    key = (psets.get("Pset_AIIFC") or {}).get("designKey")
    if not key:
        return {"found": False}
    map_path = os.path.join(
        request.app.state.settings.data_dir, "models", id, "current.map.json"
    )
    entry = None
    if os.path.isfile(map_path):
        with open(map_path, encoding="utf-8") as fh:
            entry = json.load(fh).get(key)
    if entry is None:
        return {"found": False, "designKey": key}
    return {"found": True, "designKey": key, **entry}
```

（文件头补 `import json`、`import ifcopenshell.util.element`。）

- [ ] **Step 4: 跑测试确认通过 + 全量回归**

- [ ] **Step 5: Commit** `git commit -am "feat(edit-service): locate 端点——guid→designKey→脚本调用点"`

---

### Task 4: edit-call 端点（libcst 标量重写）

**Files:**
- Create: `services/ifc/app/script_edit.py`
- Modify: `services/ifc/pyproject.toml`（dependencies 加 `"libcst>=1.5"`）
- Modify: `services/ifc/app/routes_scripts.py`（POST /models/{id}/script/edit-call）
- Test: `services/ifc/tests/test_script_edit.py`

**Interfaces:**
- Consumes: Task 3 locate 的 map 条目；staging/registry/run_script。
- Produces: `script_edit.rewrite_call_argument(script: str, line: int, argument: str, value: str | int | float | bool) -> str`（找不到调用行或参数非可改写 → ValueError）；`POST /models/{id}/script/edit-call` body `{"designKey": str, "argument": str, "value": scalar}` → 成功等同一次 PUT /script 暂存 + run。

- [ ] **Step 1: 写失败测试**

```python
def test_rewrite_literal_argument():
    from app import script_edit

    script = 'w = create_entity(model, "IfcWall", key="s1:wall:1", name="old")\n'
    out = script_edit.rewrite_call_argument(script, 1, "name", "new")
    assert '"new"' in out and '"old"' not in out


def test_rewrite_rejects_expression_value():
    from app import script_edit

    with pytest.raises(ValueError):
        script_edit.rewrite_call_argument("...\n", 1, "name", {"not": "scalar"})


def test_edit_call_endpoint_422_on_build_failure(client, model_id):
    # 合法重写但 build 失败（如把必须正的尺寸改成 -1）→ 422 且 staging 不变
    ...


def test_edit_call_success_stages_and_reruns(client, data_dir, model_id):
    # PUT + save 脚本 → edit-call 改 name → staged==1，uploads IFC 的 Name 已变
    ...
```

- [ ] **Step 2: 跑测试确认失败**（ModuleNotFoundError: script_edit）

- [ ] **Step 3: 实现 script_edit.py**

```python
# SPDX-License-Identifier: Apache-2.0
"""Targeted scalar-argument rewrite of a script factory call (libcst, lossless)."""

from __future__ import annotations

from typing import Any, Union

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider

Scalar = Union[str, int, float, bool]


def _literal(value: Scalar) -> cst.BaseExpression:
    if isinstance(value, bool):
        return cst.Name("True" if value else "False")
    if isinstance(value, (int, float)):
        return cst.Float(repr(value)) if isinstance(value, float) else cst.Integer(repr(value))
    return cst.SimpleString(repr(value))


class _ArgRewriter(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, line: int, argument: str, value: Scalar) -> None:
        super().__init__()
        self._line, self._argument, self._value = line, argument, value
        self.hit = False

    def leave_Call(self, original: cst.Call, updated: cst.Call) -> cst.Call:
        pos = self.get_metadata(PositionProvider, original, None)
        if pos is None or pos.start.line != self._line:
            return updated
        args, found = [], False
        for arg in updated.args:
            if arg.keyword and arg.keyword.value == self._argument:
                arg = arg.with_changes(value=_literal(self._value))
                found = True
            args.append(arg)
        if not found:
            args.append(cst.Arg(keyword=cst.Name(self._argument), value=_literal(self._value)))
        self.hit = True
        return updated.with_changes(args=args)


def rewrite_call_argument(script: str, line: int, argument: str, value: Any) -> str:
    """Rewrite `argument=` of the factory call starting at `line`; return new source."""
    if not isinstance(value, (str, int, float, bool)):
        raise ValueError(f"value must be a scalar literal, got {type(value).__name__}")
    rewriter = _ArgRewriter(line, argument, value)
    new_module = MetadataWrapper(cst.parse_module(script)).visit(rewriter)
    if not rewriter.hit:
        raise ValueError(f"no call found at line {line}")
    return new_module.code
```

routes_scripts.py 端点（顺序：重写 → 契约校验 → 沙箱 run → staging.push；任何失败 422 零副作用）：

```python
class EditCallBody(BaseModel):
    designKey: str
    argument: str
    value: Any  # 服务端强校验为标量


@router.post("/models/{id}/script/edit-call")
def edit_call(request: Request, body: EditCallBody, id: str = Path(pattern=MODEL_ID_PATTERN)):
    _upload_path(request, id)
    with _lock(request, id):
        staging = _staging(request, id)
        current = _current_or_409(staging)
        map_path = os.path.join(request.app.state.settings.data_dir, "models", id, "current.map.json")
        entry = None
        if os.path.isfile(map_path):
            entry = json.load(open(map_path, encoding="utf-8")).get(body.designKey)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"callsite not found: {body.designKey}")
        if entry.get("origin") == "traced":
            raise HTTPException(status_code=422, detail="callsite not auto-editable (traced); edit the script directly")
        try:
            text = script_edit.rewrite_call_argument(current, entry["line"], body.argument, body.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        _run_into_uploads(request, id, text)  # 契约校验 + 沙箱 run，失败即 422 零副作用
        staging.push(text)
        return {"modelId": id, "staged": staging.staged_count(), "script": text}
```

- [ ] **Step 4: 跑测试确认通过 + 全量回归 + `uv lock` 更新依赖**

- [ ] **Step 5: Commit** `git commit -am "feat(edit-service): edit-call 端点——libcst 标量重写 + 沙箱验证 + 暂存"`

---

### Task 5: 契约条款 C-locate / C-scalar 入 skill

**Files:**
- Modify: `skills/aiifc/SKILL.md`（MUST 清单追加 #30 C-locate、#31 C-scalar）
- Modify: `skills/aiifc/templates/build_script_template.py`（注释示例统一走 create_entity）
- Test: `tests/skill/test_script_contract.py`（断言新条款文本存在）

**Interfaces:**
- Produces: 契约条款文本标记 `C-locate` / `C-scalar`（打包测试断言锚点）。

- [ ] **Step 1: 写失败测试**——tests/skill/test_script_contract.py 加：

```python
def test_contract_has_locatability_clauses():
    text = Path("skills/aiifc/SKILL.md").read_text(encoding="utf-8")
    assert "C-locate" in text
    assert "C-scalar" in text
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**——SKILL.md MUST 清单追加（沿用 #25-29 编号风格）：

```markdown
30. **C-locate（创建点可定位）**：审查可见构件必须经 `script_lib.create_entity(...)` 创建；禁止绕过工厂直接 `root.create_entity`——工厂记录调用点供 web 端「选中构件→定位脚本」。
31. **C-scalar（web 可编辑参数为标量）**：需要 web 端编辑的参数必须是标量字面量或 `params` 引用；表达式参数只能手改脚本（edit-call 拒绝）。
```

模板示例注释同步。

- [ ] **Step 4: 跑测试确认通过 + `python -m pytest tests/skill/ -q` 全量**

- [ ] **Step 5: Commit** `git commit -am "feat(skill): 契约追加 C-locate / C-scalar 条款"`

---

## Phase 2 — 存储与 bootstrap

### Task 6: IFC 只物化最新 + 历史按需重建

**Files:**
- Modify: `services/ifc/app/script_versions.py`（save 后清理旧 IFC 快照）
- Modify: `services/ifc/app/routes_diff.py:38-42`（_version_or_404 → 缺失且有脚本则沙箱重建入缓存）
- Test: `services/ifc/tests/test_ifc_lazy_materialize.py`

**Interfaces:**
- Produces: `{data_dir}/models/{id}/ifc_cache/v{n}.ifc`（LRU 上限 4）；`materialize_version(data_dir, model_id, version, settings) -> str`（routes_diff 与下载路径共用）。

- [ ] **Step 1: 写失败测试**

```python
def test_save_removes_older_ifc_snapshots(client, data_dir, model_id):
    # save v1 → save v2 → versions/ 下只剩 v2.ifc；v1.ifc 不存在，v1.py/v1.map.json 在
    ...


def test_diff_old_version_rebuilds_from_script(client, data_dir, model_id):
    # v1.ifc 已被清理 → POST /diff {base: v1, target: v2} → 200 且 ifc_cache/v1.ifc 生成
    ...


def test_rebuilt_ifc_semantically_empty_diff(client, data_dir, model_id):
    # 迁移期保留的原 v1.ifc 与重建产物 compute_diff 为空（确定性验证，I5）
    ...
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**——save 成功后删 `versions/v{<n}.ifc` 中有对应 `scripts/v{m}.py` 者；routes_diff 的版本解析失败时查 `script_versions.script_path`，存在则 `script_runner.run_script(settings, script, ifc_cache/v{n}.ifc)` 后返回缓存路径（缓存超 4 个删最旧，按 mtime）。

- [ ] **Step 4: 全量回归**（重点 test_diff.py / test_script_staging.py 的成对断言需同步更新）

- [ ] **Step 5: Commit** `git commit -am "feat(edit-service): IFC 只物化最新大版本，历史按需重建 + LRU 缓存（I5）"`

---

### Task 7: bootstrap 原件保留 + 对齐报告

**Files:**
- Modify: `services/ifc/app/routes_scripts.py`（stage_script 首暂存时保留原件；save_script 响应带 alignment）
- Test: `services/ifc/tests/test_bootstrap_alignment.py`

**Interfaces:**
- Produces: `{data_dir}/models/{id}/bootstrap.ifc`（plain 态首次 PUT /script 时从 uploads 复制）；save 响应增 `alignment: {"added": int, "removed": int, "changed": int} | None`。

- [ ] **Step 1: 写失败测试**——plain 模型 PUT /script 后 bootstrap.ifc 存在；save 响应 alignment 字段为计数三元组；已有版本模型不产生 bootstrap.ifc 且 alignment 为 None。

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**——stage_script 内 push 前：`if not script_versions.list_scripts(...) and not staging.history and not os.path.exists(bootstrap_path): shutil.copyfile(uploads, bootstrap_path)`；save_script 内版本落盘后：bootstrap.ifc 存在则 `diffing.compute_diff(bootstrap, ifc_path)`，计数入响应。

- [ ] **Step 4: 全量回归 + gen:api / check:api**

- [ ] **Step 5: Commit** `git commit -am "feat(edit-service): bootstrap 原件保留 + save 对齐报告"`

---

## Phase 3 — 退役与前端/文档

### Task 8: L1 直改链路退役（410）

**Files:**
- Modify: `services/ifc/app/routes_edits.py`（PUT/DELETE entities、editable-schema、commit → 410）
- Modify: `server/internal/api/edit.go:32-40`（对应代理路由移除）+ `edit_test.go`
- Test: `services/ifc/tests/test_edits_retired.py`（先写）

**注意**：`POST /models/{id}/diff/upload`（routes_user_edits，MCP 用户修改解析）保留——只读解析，非直改。pending 回放内部机制（W-0009）随 script run 仍需要，pending.py 保留但对外端点退役。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.parametrize("method,path", [
    ("PUT", "/models/{id}/edit/entities/g1"),
    ("DELETE", "/models/{id}/edit/entities/g1"),
    ("GET", "/models/{id}/edit/entities/g1/editable-schema"),
    ("POST", "/models/{id}/edit/commit"),
])
def test_direct_edit_endpoints_gone(client, model_id, method, path):
    r = client.request(method, path.format(id=model_id), json={})
    assert r.status_code == 410
```

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**——各 handler 替换为 `raise HTTPException(status_code=410, detail="direct IFC editing retired: edit the build script (script-as-source)")`；server 侧删 edit.go 对应路由与编排，edit_test.go 改为断言 404（路由不存在）或同步 410；旧编辑测试（test_edits.py 等）删除或改写为退役断言。

- [ ] **Step 4: 回归** `uv run --group dev pytest` + `go test ./...` + `npm run check:api`

- [ ] **Step 5: Commit** `git commit -am "feat!: 直改链路退役（410）——统一 script-as-source 编辑"`

---

### Task 9: web 前端——locate 跳转 + 直改入口隐藏

**Files:**
- Modify: `web/src/`（PropertyPanel 编辑表单移除、保留只读；选中构件加「定位脚本」按钮 → 请求 locate → DesignPanel 脚本编辑器跳行；origin=params 时聚焦 PARAMS 表单项）
- Test: 对应 `*.test.tsx`（locate API store、跳转逻辑；MockEventSource 模式参考 W-0002）

- [ ] **Step 1: 写失败测试**（api 层 locate 封装 + 点击跳转行号传入编辑器 store）

- [ ] **Step 2: 跑测试确认失败**

- [ ] **Step 3: 实现**（遵循现有 zustand store 与 DesignPanel 结构；脚本编辑器跳行用其现有 cursor API）

- [ ] **Step 4: `npm test && npm run lint && npm run build`**

- [ ] **Step 5: Commit** `git commit -am "feat(web): 选中构件定位脚本调用点 + 直改入口隐藏"`

---

### Task 10: 文档同步

**Files:**
- Modify: `docs/site/viewer/editing.md`（重写为脚本编辑流）、`docs/site/reference/design-edit.md`（locate/edit-call/bootstrap）、`docs/site/viewer/versions-diff.md`（三件成对 + IFC 缓存语义）、`README.md` / `README.zh-CN.md`（Key Advantages）、`AGENTS.md`（组件表/API 契约节）
- 英文 locale 对应页同步最小改动（方向性描述）

- [ ] **Step 1: `cd docs && npm run gen:api && npm run check:api`**
- [ ] **Step 2: 逐页改写（内容以 spec §6/§9/§10 为准）**
- [ ] **Step 3: `npm run docs:build` 验证**
- [ ] **Step 4: Commit** `git commit -am "docs: 统一编辑模型文档同步"`

---

## Self-Review 记录

- Spec 覆盖：I1-I5 → Tasks 1-8；状态机各转移 → Tasks 3/4/8 测试；契约条款 → Task 5；存储策略 → Task 6；bootstrap → Task 7；文档清单 §10 → Task 10。无缺口。
- 类型一致性：`rewrite_call_argument` / `run_script(..., map_out=)` / `save(..., map_text=)` / locate 响应字段跨任务一致。
- 已知留白：Task 9 前端代码细节在实施时按现有 DesignPanel/PropertyPanel 结构落地（计划有意不越俎代庖组件内部结构，接口锚点已固定）。
