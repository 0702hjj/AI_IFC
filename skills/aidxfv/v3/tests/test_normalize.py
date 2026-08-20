"""normalize.py 测试（T13 skeleton 半 + T14 rooms 半）。"""

import pytest

from floorgeom.normalize import SchemaError, normalize_skeleton, normalize_rooms


MODULUS = 100


def _skeleton_doc(**overrides):
    doc = {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": MODULUS},
        "zones": [{
            "zone": "podium",
            "outline": [
                {"outer": {"vertices": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]}}
            ],
            "core": {"anchor": [28000, 12000],
                     "vertices": [[24000, 10000], [32000, 10000], [32000, 20000], [24000, 20000]]},
            "corridor": {"form": "path", "width_mm": 3000,
                         "path": {"edges": {
                             "west": [[16000, 4000], [16000, 24000]],
                             "north": [[16000, 24000], [44000, 24000]],
                             "east": [[44000, 24000], [44000, 4000]],
                             "south": [[44000, 4000], [16000, 4000]]}}},
            "main_partitions": [
                {"id": "cut:0", "role": "shop|arcade 分界",
                 "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
                 "to": {"ref": "outline:edge:0", "at": 0.5}}
            ],
            "special_openings": [],
            "typology": "中庭环绕",
            "typology_reason": "holes[0] 居中",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        }],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestNormalizeSkeleton:
    def test_podium_full(self):
        """T13 正例：podium 全量 → 几何模型。"""
        m = normalize_skeleton(_skeleton_doc())
        assert "frame" in m
        assert "zones" in m
        z = m["zones"][0]
        assert z["zone"] == "podium"
        assert "axis_grid" in z and "core" in z and "corridor" in z



    def test_core_anchor_locked(self):
        """T4：锚点原值不动，snap 不移动锚点。"""
        m = normalize_skeleton(_skeleton_doc())
        z = m["zones"][0]
        assert z["core"]["anchor"] == [28000, 12000]

    def test_core_null(self):
        """G-01：core=null 无核心筒。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = None
        m = normalize_skeleton(doc)
        assert m["zones"][0]["core"] is None


class TestMultiCore:
    """多核心筒（2026-08-12 用户拍板：住宅多单元并排楼有多个楼梯间核心筒，
    如 data/gold/住宅楼.dxf 一梯两户×2 单元）。
    core 输入接受 单对象|数组|null；输出 cores 数组（总是），
    core 键保持兼容（单 core=对象，多 core=首个，null=None）。"""

    def _two_core_doc(self):
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = [
            {"anchor": [9700, 10500], "extent": {"x": [1, 2], "y": [1, 2]}},
            {"anchor": [32800, 13500], "extent": {"x": [4, 5], "y": [1, 2]}},
        ]
        return doc



    def test_single_core_also_has_cores(self):
        """单 core 输入也产 cores（=[core]），向后兼容。"""
        m = normalize_skeleton(_skeleton_doc())
        z = m["zones"][0]
        assert z["cores"] == [z["core"]] or z["cores"][0] == z["core"]

    def test_core_null_cores_empty(self):
        """core=null → cores=[]。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = None
        m = normalize_skeleton(doc)
        assert m["zones"][0]["cores"] == []




    def test_anchor_not_snapped(self):
        """T4 变体：anchor 带非模数值也不被 snap 移动。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"]["anchor"] = [28123, 11977]  # 非模数
        m = normalize_skeleton(doc)
        assert m["zones"][0]["core"]["anchor"] == [28123, 11977]

    def test_deterministic(self):
        """同输入同输出（canon 字节一致）。"""
        a = normalize_skeleton(_skeleton_doc())
        b = normalize_skeleton(_skeleton_doc())
        assert a == b


