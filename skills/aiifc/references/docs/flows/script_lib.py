"""script_lib.py — 构建脚本公共 helper(script-as-source 契约的实现层)。

契约(见 SKILL.md MUST #25-29):
- 脚本头部有 `PARAMS = {...}` 顶层字面量 dict(JSON-compatible, 所有可调参数集中于此)
- 构件 GlobalId = deterministic_guid(key); key 稳定唯一 `{storey}:{kind}:{n}`, 写 Pset_AIIFC.designKey
- 入口 `build(params, out_path)`; `__main__` 用 PARAMS 调 build
- 出口经 write_and_validate(model.write + ifcopenshell.validate)

build_script_template.py 是本模块的薄封装(features.json → IFC)。
validate_script_contract(path) 静态检查脚本是否符合上述契约(ast 解析, 不执行脚本)。

用法:
    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from script_lib import (deterministic_guid, create_entity, attach_design_key,
                            create_skeleton, write_and_validate)
"""
import ast
import json
import uuid
from pathlib import Path

import ifcopenshell
import ifcopenshell.api
import ifcopenshell.validate
import ifcopenshell.guid as ifc_guid

api = ifcopenshell.api.run

# 确定性 GlobalId 的命名空间(固定不变; 改动会使所有已生成模型的 GlobalId 变化)
NAMESPACE_AI_IFC = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def deterministic_guid(key: str) -> str:
    """由稳定 key 派生确定性 GlobalId(IFC base64 22 字符, 首字符 0-3)。

    同一 key 多次运行 GlobalId 不变(确定性)。IFC base64 编码用 ifcopenshell.guid.compress。
    """
    return ifc_guid.compress(str(uuid.uuid5(NAMESPACE_AI_IFC, key)))


def create_entity(model, ifc_class: str, key: str, **kwargs):
    """创建实体并写入确定性 GlobalId(create_entity 不接受 GlobalId 参数)。"""
    product = api("root.create_entity", model, ifc_class=ifc_class, **kwargs)
    product.GlobalId = deterministic_guid(key)
    return product


def attach_design_key(model, product, key: str):
    """把 key 写入 Pset_AIIFC.designKey(IFC ↔ 脚本/版本 双向映射)。"""
    if not key:
        return
    pset = api("pset.add_pset", model, product=product, name="Pset_AIIFC")
    api("pset.edit_pset", model, pset=pset,
        properties={"designKey": key, "designId": str(product.GlobalId)[:8]})


def create_skeleton(model, name: str = "building", storeys: dict | None = None):
    """骨架: units + Model/Body context + Project→Site→Building→Storey 聚合树。

    storeys: {名字: 标高(米)}; None → 无 storey。返回 (body_context, {名字: storey 实体})。
    """
    prj = api("root.create_entity", model, ifc_class="IfcProject", name=name)
    api("unit.assign_unit", model)
    m3d = api("context.add_context", model, context_type="Model")
    body = api("context.add_context", model, context_identifier="Body",
               target_view="MODEL_VIEW", parent=m3d)
    site = api("root.create_entity", model, ifc_class="IfcSite", name="Site")
    bldg = api("root.create_entity", model, ifc_class="IfcBuilding", name=name)
    api("aggregate.assign_object", model, relating_object=prj, products=[site])
    api("aggregate.assign_object", model, relating_object=site, products=[bldg])
    smap = {}
    for sn, elev in (storeys or {}).items():
        st = api("root.create_entity", model, ifc_class="IfcBuildingStorey", name=sn)
        st.Elevation = elev * 1000
        api("aggregate.assign_object", model, relating_object=bldg, products=[st])
        smap[sn] = st
    return body, smap


def write_and_validate(model, out_path) -> bool:
    """出口: model.write 后接 ifcopenshell.validate(产物必须过 schema 校验)。"""
    model.write(out_path)
    lg = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(out_path, lg)
    return not lg.statements


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
