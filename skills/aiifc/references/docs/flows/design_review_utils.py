"""
design_review_utils.py — design_review 基础工具（安全取值/世界坐标/区间重叠）。

拆分自 design_review.py（W-0049 文件行数门控），mixin 由 flows.design_review.DesignReviewer 组合。
"""

import numpy as np
import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.element

try:  # 包内导入(example: from flows.design_review import run)
    from flows.ifc_inspect import _scan_element
except ImportError:  # 独立运行(python docs/flows/design_review.py)
    try:
        from ifc_inspect import _scan_element
    except ImportError:
        _scan_element = None


# ═══ 基础工具 ═══

def _world_pos(element) -> tuple:
    """计算元素的世界坐标 (x, y, z),模型单位。"""
    if not element.ObjectPlacement:
        return (0.0, 0.0, 0.0)
    m = np.array(ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement))
    return (round(float(m[0][3]), 3), round(float(m[1][3]), 3), round(float(m[2][3]), 3))


def _has_body(element) -> bool:
    """检查元素是否有 Body 几何表示。"""
    if not element.Representation:
        return False
    for rep in element.Representation.Representations:
        if rep.RepresentationIdentifier == "Body":
            return True
    return False


def _get_psets_safe(element):
    try:
        return ifcopenshell.util.element.get_psets(element)
    except Exception:
        return {}


def _get_material_safe(element):
    try:
        return ifcopenshell.util.element.get_material(element)
    except Exception:
        return None


def _get_container_safe(element):
    try:
        return ifcopenshell.util.element.get_container(element)
    except Exception:
        return None


def _by_type_safe(model, cls) -> list:
    """schema 安全的 by_type:IFC2x3 无 IfcFurniture 等类时返回空表。"""
    try:
        return model.by_type(cls)
    except RuntimeError:
        return []


def _overlap(a, b) -> float:
    """两区间 [a0,a1] [b0,b1] 的重叠长度。"""
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
