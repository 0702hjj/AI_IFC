"""
ModelStateTracker — 轻量级建模状态追踪器。

在建模过程中每步操作后调用 snapshot(),生成几何状态 JSON。
LLM 直接读 JSON 验证位置,不需要理解 4×4 矩阵或 Placement 父子链。

用法:
    from flows.tracker import ModelStateTracker
    tracker = ModelStateTracker(model)

    # 每步操作后
    tracker.snapshot(step_name="walls_created")

    # 读最后快照
    state = tracker.latest()
    print(json.dumps(state, indent=2))
"""

import json
import numpy as np
import ifcopenshell
import ifcopenshell.util.placement
import ifcopenshell.util.element


def _world_pos(element) -> tuple:
    """计算元素的世界坐标(x, y, z in mm),通过父链矩阵乘积。"""
    if not element.ObjectPlacement:
        return (0.0, 0.0, 0.0)
    m = np.array(ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement))
    return (round(float(m[0][3]), 1), round(float(m[1][3]), 1), round(float(m[2][3]), 1))


def _has_body(element) -> bool:
    """检查元素是否有 Body 几何表示。"""
    if not element.Representation:
        return False
    for rep in element.Representation.Representations:
        if rep.RepresentationIdentifier == "Body":
            return True
    return False


def _element_info(element, model) -> dict:
    """提取单个元素的关键信息。"""
    info = {
        "guid": element.GlobalId,
        "class": element.is_a(),
        "name": element.Name if hasattr(element, "Name") and element.Name else None,
        "world_xyz_mm": list(_world_pos(element)),
        "has_body": _has_body(element),
    }
    # 容器
    try:
        container = ifcopenshell.util.element.get_container(element)
        info["container"] = container.Name if container else None
    except Exception:
        info["container"] = None
    return info


class ModelStateTracker:
    """轻量级建模状态追踪器。每步操作后调用 snapshot() 记录状态。"""

    def __init__(self, model: ifcopenshell.file):
        self.model = model
        self._steps: list[dict] = []

    def snapshot(self, step_name: str) -> dict:
        """生成当前模型状态的快照。"""
        state = {
            "step": step_name,
            "storeys": [],
            "walls": [],
            "slabs": [],
            "openings": [],
            "doors": [],
            "windows": [],
            "types": [],
            "relationships": [],
        }

        # Storeys
        for storey in self.model.by_type("IfcBuildingStorey"):
            state["storeys"].append({
                "guid": storey.GlobalId,
                "name": storey.Name,
                "elevation": storey.Elevation,
            })

        # Walls
        for wall in self.model.by_type("IfcWall"):
            state["walls"].append(_element_info(wall, self.model))

        # Slabs
        for slab in self.model.by_type("IfcSlab"):
            state["slabs"].append(_element_info(slab, self.model))

        # Openings
        for opening in self.model.by_type("IfcOpeningElement"):
            info = _element_info(opening, self.model)
            # 宿主墙
            for oh in opening.VoidsElements:
                host = oh.RelatingBuildingElement
                info["voids_wall"] = host.GlobalId
                info["voids_wall_class"] = host.is_a()
            state["openings"].append(info)

        # Doors
        for door in self.model.by_type("IfcDoor"):
            info = _element_info(door, self.model)
            info["overall_height"] = door.OverallHeight
            info["overall_width"] = door.OverallWidth
            info["predefined_type"] = door.PredefinedType
            # 填充的洞口
            for fv in door.FillsVoids:
                opening = fv.RelatingOpeningElement
                info["fills_opening"] = opening.GlobalId
            state["doors"].append(info)

        # Windows
        for window in self.model.by_type("IfcWindow"):
            info = _element_info(window, self.model)
            info["overall_height"] = window.OverallHeight
            info["overall_width"] = window.OverallWidth
            info["predefined_type"] = window.PredefinedType
            for fv in window.FillsVoids:
                opening = fv.RelatingOpeningElement
                info["fills_opening"] = opening.GlobalId
            state["windows"].append(info)

        # Types
        for wall_type in self.model.by_type("IfcWallType"):
            state["types"].append({
                "guid": wall_type.GlobalId,
                "name": wall_type.Name,
                "predefined_type": wall_type.PredefinedType,
            })

        # Key relationships summary
        for rel in self.model.by_type("IfcRelVoidsElement"):
            state["relationships"].append({
                "type": "IfcRelVoidsElement",
                "host": rel.RelatingBuildingElement.GlobalId,
                "host_class": rel.RelatingBuildingElement.is_a(),
                "opening": rel.RelatedOpeningElement.GlobalId,
            })
        for rel in self.model.by_type("IfcRelFillsElement"):
            state["relationships"].append({
                "type": "IfcRelFillsElement",
                "opening": rel.RelatingOpeningElement.GlobalId,
                "filling": rel.RelatedBuildingElement.GlobalId,
                "filling_class": rel.RelatedBuildingElement.is_a(),
            })

        self._steps.append(state)
        return state

    def latest(self) -> dict:
        """返回最近一次的快照。"""
        if not self._steps:
            return {}
        return self._steps[-1]

    def all_steps(self) -> list[dict]:
        """返回所有步骤的快照。"""
        return self._steps

    def to_json(self, step_name: str = None) -> str:
        """导出为 JSON 字符串。"""
        if step_name:
            state = self.snapshot(step_name)
        else:
            state = self.latest()
        return json.dumps(state, indent=2, ensure_ascii=False, default=str)

    def check_geometry(self, step_name: str = "check") -> dict:
        """验证所有产品都有几何体,返回验证报告。"""
        state = self.snapshot(step_name)
        issues = []

        for wall in state["walls"]:
            if not wall["has_body"]:
                issues.append(f"wall {wall['guid'][:8]} has no body geometry")

        for door in state["doors"]:
            if not door["has_body"]:
                issues.append(f"door {door['guid'][:8]} has no body geometry")
            if "fills_opening" not in door:
                issues.append(f"door {door['guid'][:8]} not linked to any opening")

        for window in state["windows"]:
            if not window["has_body"]:
                issues.append(f"window {window['guid'][:8]} has no body geometry")
            if "fills_opening" not in window:
                issues.append(f"window {window['guid'][:8]} not linked to any opening")

        for opening in state["openings"]:
            if not opening["has_body"]:
                issues.append(f"opening {opening['guid'][:8]} has no body geometry")
            if "voids_wall" not in opening:
                issues.append(f"opening {opening['guid'][:8]} not linked to any wall")

        state["validation"] = {
            "ok": len(issues) == 0,
            "issues": issues,
        }
        return state
