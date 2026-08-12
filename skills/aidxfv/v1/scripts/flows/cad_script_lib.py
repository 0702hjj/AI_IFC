# SPDX-License-Identifier: AGPL-3.0-only
"""cad_script_lib.py — DXF 构建脚本公共 helper(services/cad script-as-source 契约层)。

契约(见 skills/aidxfv/v1/SKILL.md「services/cad 脚本契约」节, 镜像 aiifc script_lib):
- 脚本头部有 `PARAMS = {...}` 顶层字面量 dict(JSON-compatible, 所有可调参数集中于此)
- 实体稳定身份 = XDATA 确定性 key(APPID ``AIDXF``); DXF handle 由 CAD 软件分配、
  重存全变, 不能当身份用; key 格式 `{layer}:{kind}:{n}`(kind 小写, n 从 1 起),
  add_entity 自动分配并写 XDATA
- 入口 `build(params, out_path)`; `__main__` 用 PARAMS 调 build
- 出口经 write_and_validate(doc.saveas + doc.audit), 同时落裸 ScriptMap 侧车
  `out.dxf.map.json`(key → {line, col, snippet, origin, params_keys};
  信封包装由 services/cad 沙箱负责)

validate_script_contract(path) 静态检查脚本是否符合上述契约(ast 解析, 不执行脚本)。

用法:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cad_script_lib import (APPID, reset_state, add_entity, get_entity_key,
                                write_and_validate, validate_script_contract)
"""
import ast
import inspect
import json
import linecache
import uuid
from collections import OrderedDict
from pathlib import Path

APPID = "AIDXF"

# 确定性 key 派生的命名空间(固定不变; 改动会使所有已生成图纸的身份变化)
NAMESPACE_AIDXF = uuid.UUID("8f2e1c4a-3b5d-4e6f-9a0b-1c2d3e4f5a6b")

# add_entity 调用点登记(key → {"line","col","snippet","origin","params_keys"});
# 出口落 .map.json
_CALLSITES: "OrderedDict[str, dict]" = OrderedDict()

# 自动 key 计数器: (layer, kind) → 已分配数量
_KEY_COUNTERS: "dict[tuple[str, str], int]" = {}

# kind → (msp 工厂方法名, 必填 kwarg 元组)
_KIND_SPECS = {
    "LINE": ("add_line", ("start", "end")),
    "CIRCLE": ("add_circle", ("center", "radius")),
    "ARC": ("add_arc", ("center", "radius", "start_angle", "end_angle")),
    "LWPOLYLINE": ("add_lwpolyline", ("points",)),
    "TEXT": ("add_text", ("text",)),
    "MTEXT": ("add_mtext", ("text",)),
    "INSERT": ("add_blockref", ("name", "insert")),
}


def reset_state() -> None:
    """清 _CALLSITES 与 key 计数器(沙箱/测试每次跑前调, 保证确定性)。"""
    _CALLSITES.clear()
    _KEY_COUNTERS.clear()


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


def _params_ref_keys(line: str) -> list[str]:
    """从调用行源码提取 params/PARAMS 下标引用键（保序去重）。

    规则（与 aiifc script_lib 同形）：收集调用参数（位置参数/关键字值）里
    ``params[...]`` / ``PARAMS[...]`` 下标引用——多级下标取首键
    （``params["a"]["b"]`` → "a"）、引用嵌套于其他下标表达式也纳入
    （``keys[params["k"]]`` → "k"）。语法错误/无引用 → []。
    """
    try:
        tree = ast.parse(line)
    except SyntaxError:
        return []
    call = next((n for n in ast.walk(tree) if isinstance(n, ast.Call)), None)
    if call is None:
        return []
    keys: list[str] = []
    seen: set[str] = set()
    for node in ast.walk(call):
        if not isinstance(node, ast.Subscript):
            continue
        base = node.value
        if isinstance(base, ast.Subscript):
            continue  # 外层下标（首键由直接作用于 Name 的内层下标取）
        if not (isinstance(base, ast.Name) and base.id in ("params", "PARAMS")):
            continue
        if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            continue
        key = node.slice.value
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _extract_params_keys(filename: str, lineno: int) -> list[str]:
    """origin=params 时读取调用行并提取 params_keys（供 PARAMS 表单聚焦）。"""
    return _params_ref_keys(linecache.getline(filename, lineno).strip())


def _record_callsite(key: str, caller_hop: int = 2) -> None:
    """记录 add_entity 调用点（用户脚本帧 = 本函数调用者的调用者，hop=2）。

    caller_hop 显式化帧语义：add_entity 直接调本函数，
    用户脚本帧都在 hop=2（f_back.f_back）；hop=1 保留给用户帧直接调用场景。
    """
    frame = inspect.currentframe()
    try:
        caller = frame
        for _ in range(caller_hop):
            if caller is None:
                break
            caller = caller.f_back
        if caller is None or not key:
            return
        info = inspect.getframeinfo(caller, context=1)
        snippet = (info.code_context or [""])[0].strip()
        origin = _classify_origin(caller.f_code.co_filename, info.lineno)
        params_keys = (
            _extract_params_keys(caller.f_code.co_filename, info.lineno)
            if origin == "params"
            else []
        )
        _CALLSITES[key] = {
            "line": info.lineno,
            "col": info.index or 0,
            "snippet": snippet,
            "origin": origin,
            "params_keys": params_keys,
        }
    finally:
        del frame


def _allocate_key(layer: str, kind: str) -> str:
    """自动分配确定性 key: `{layer}:{kind_lower}:{n}`(同 layer:kind 递增, n 从 1 起)。"""
    ck = (layer, kind.lower())
    n = _KEY_COUNTERS.get(ck, 0) + 1
    _KEY_COUNTERS[ck] = n
    return f"{layer}:{kind.lower()}:{n}"


def add_entity(msp, kind: str, layer: str = "0", key: "str | None" = None, **kwargs):
    """创建 DXF 实体并写入 XDATA 确定性 key(APPID ``AIDXF``)。

    kind 大写分派: LINE(start, end) / CIRCLE(center, radius) /
    ARC(center, radius, start_angle, end_angle) /
    LWPOLYLINE(points, closed=False, format=...) / TEXT(text, insert, height=2.5) /
    MTEXT(text, insert) / INSERT(name, insert)。layer 经 dxfattribs 传入。
    key=None 时自动分配 `{layer}:{kind}:{n}`(reset_state 后重跑序列全同, 确定性);
    显式 key= 优先于自动分配。未知 kind 抛 ValueError。
    """
    kind_u = kind.upper()
    spec = _KIND_SPECS.get(kind_u)
    if spec is None:
        raise ValueError(
            f"未知实体类型: {kind}(支持 {', '.join(sorted(_KIND_SPECS))})")
    method_name, required = spec
    missing = [r for r in required if r not in kwargs]
    if missing:
        raise ValueError(f"{kind_u} 缺少必填参数: {', '.join(missing)}")
    args = dict(kwargs)
    attribs = args.pop("dxfattribs", None) or {}
    attribs.setdefault("layer", layer)
    extra = {}
    if kind_u == "LWPOLYLINE":
        if args.pop("closed", False):
            extra["close"] = True
        fmt = args.pop("format", None)
        if fmt is not None:
            extra["format"] = fmt
    elif kind_u == "TEXT":
        attribs.setdefault("insert", args.pop("insert", (0, 0)))
        attribs.setdefault("height", args.pop("height", 2.5))
    elif kind_u == "MTEXT":
        attribs.setdefault("insert", args.pop("insert", (0, 0)))
    doc = msp.doc
    if APPID not in doc.appids:
        doc.appids.add(APPID)
    if key is None:
        key = _allocate_key(layer, kind_u)
    _record_callsite(key)
    positional = [args.pop(r) for r in required if r != "insert"] if kind_u != "LWPOLYLINE" \
        else [args.pop("points")]
    entity = getattr(msp, method_name)(*positional, **extra, **args,
                                       dxfattribs=attribs)
    entity.set_xdata(APPID, [(1000, key)])
    return entity


def get_entity_key(entity) -> "str | None":
    """读回实体的 XDATA key; 无 XDATA / 异常 → None。"""
    try:
        if not entity.has_xdata(APPID):
            return None
        for tag in entity.get_xdata(APPID):
            if tag.code == 1000:
                return tag.value
    except Exception:
        return None
    return None


def write_and_validate(doc, out_path) -> bool:
    """出口: doc.saveas 后接 doc.audit, 并落裸 ScriptMap 侧车 .map.json。"""
    doc.saveas(out_path)
    auditor = doc.audit()
    has_errors = auditor.has_errors
    if callable(has_errors):
        has_errors = has_errors()
    map_path = str(out_path) + ".map.json"
    Path(map_path).write_text(
        json.dumps(_CALLSITES, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return not has_errors


def _is_json_compatible(value) -> bool:
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def validate_script_contract(path) -> list[str]:
    """静态检查构建脚本是否符合 script-as-source 契约(ast 解析, 不执行)。

    返回错误信息列表; 空列表 = 通过。检查项:
    - 可解析为 Python
    - 顶层 `PARAMS = {...}` 字面量 dict 且 JSON-compatible
    - 顶层 `build(params, out_path)` 入口函数
    - `if __name__ == "__main__":` 守卫
    """
    errors: list[str] = []
    src = Path(path).read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        return [f"语法错误: {exc}"]

    params_node = None
    has_build = False
    has_main = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PARAMS":
                    params_node = node.value
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "build":
            has_build = True
            if len(node.args.args) < 2:
                errors.append("build 入口签名应为 build(params, out_path)")
        elif isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"):
                has_main = True

    if params_node is None:
        errors.append("缺少顶层 PARAMS = {...} 字面量 dict")
    else:
        if not isinstance(params_node, ast.Dict):
            errors.append("PARAMS 必须是顶层字面量 dict")
        else:
            try:
                value = ast.literal_eval(params_node)
            except (ValueError, TypeError):
                errors.append("PARAMS 必须是字面量(不得含表达式/调用)")
            else:
                if not _is_json_compatible(value):
                    errors.append("PARAMS 必须 JSON-compatible")

    if not has_build:
        errors.append("缺少顶层 build(params, out_path) 入口函数")
    if not has_main:
        errors.append('缺少 if __name__ == "__main__": 守卫(__main__ 应用 PARAMS 调 build)')
    return errors
