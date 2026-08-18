"""plan.schema.json v3.1 正反例（本 skill 自持 schema，即契约事实源）。

v3.1（2026-08-09）：holes 升级 ring——开孔与 outer 同等表达力：
- 纯顶点数组（直边孔简写，v3 兼容）；
- {"vertices", "arcs?"}（真弧孔洞，整圆 = circle_ring 规范形）。
"""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA = json.loads(
    (Path(__file__).resolve().parent.parent / "references" / "schemas" / "plan.schema.json")
    .read_text(encoding="utf-8")
)


@pytest.fixture(scope="module")
def validator():
    return Draft202012Validator(SCHEMA)


def _plan() -> dict:
    """最小合法 plan（单 zone 矩形轮廓）。"""
    return {
        "version": 3,
        "project": "schema-v31-test",
        "site": {
            "lot_polygon_mm": [[0, 0], [100000, 0], [100000, 80000], [0, 80000]],
            "setbacks_mm": {"front": 0, "rear": 0, "left": 0, "right": 0},
        },
        "zones": [
            {
                "id": "z1",
                "function": "retail",
                "floors": {"from": 1, "to": 1},
                "floor_height_mm": 4800,
                "outline_mm": [
                    {"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]]}
                ],
                "program": [{"room": "shop"}],
            }
        ],
    }


def _with_hole(hole) -> dict:
    p = _plan()
    p["zones"][0]["outline_mm"][0]["holes"] = [hole]
    return p


# ── 正例 ──────────────────────────────────────────────────────────


def test_plain_polygon_hole_still_valid(validator):
    """v3 直边孔简写（纯顶点数组）兼容不破。"""
    validator.validate(_with_hole([[14000, 11000], [26000, 11000], [26000, 19000], [14000, 19000]]))


def test_ring_hole_with_arcs_valid(validator):
    """v3.1 ring 孔洞（顶点 + 弧标注）通过。"""
    ring = {
        "vertices": [[14000, 11000], [26000, 11000], [26000, 19000], [14000, 19000]],
        "arcs": [{"at": 1, "center": [26000, 15000], "radius": 4000, "a0": -90, "a1": 90}],
    }
    validator.validate(_with_hole(ring))


def test_circle_ring_hole_valid(validator):
    """整圆规范形（3 顶点 + 3×120° 弧）通过。"""
    ring = {
        "vertices": [[26000, 15000], [17000, 20196], [17000, 9804]],
        "arcs": [
            {"at": 0, "center": [20000, 15000], "radius": 6000, "a0": 0, "a1": 120},
            {"at": 1, "center": [20000, 15000], "radius": 6000, "a0": 120, "a1": 240},
            {"at": 2, "center": [20000, 15000], "radius": 6000, "a0": 240, "a1": 360},
        ],
    }
    validator.validate(_with_hole(ring))


# ── 反例 ──────────────────────────────────────────────────────────


def test_ring_missing_vertices_rejected(validator):
    with pytest.raises(ValidationError):
        validator.validate(_with_hole({"arcs": []}))


def test_ring_extra_field_rejected(validator):
    ring = {"vertices": [[14000, 11000], [26000, 11000], [26000, 19000]], "foo": 1}
    with pytest.raises(ValidationError):
        validator.validate(_with_hole(ring))


def test_ring_arc_missing_center_rejected(validator):
    ring = {
        "vertices": [[14000, 11000], [26000, 11000], [26000, 19000]],
        "arcs": [{"at": 1, "radius": 4000}],
    }
    with pytest.raises(ValidationError):
        validator.validate(_with_hole(ring))


def test_ring_arc_bad_at_rejected(validator):
    ring = {
        "vertices": [[14000, 11000], [26000, 11000], [26000, 19000]],
        "arcs": [{"at": -1, "center": [26000, 15000], "radius": 4000}],
    }
    with pytest.raises(ValidationError):
        validator.validate(_with_hole(ring))



# ── v3.1+ core（统一 ring：与 outer/holes 同类型）──


def _with_core(core) -> dict:
    p = _plan()
    p["zones"][0]["core"] = core
    return p


def test_core_polygon_shorthand_valid(validator):
    """core = 纯顶点数组（polygon 简写）通过——与 holes 同形态。"""
    validator.validate(_with_core([[27000,16000],[33000,16000],[33000,24000],[27000,24000]]))


def test_core_ring_with_arcs_valid(validator):
    """core = ring object（带弧）通过——圆形电梯井。"""
    ring = {"vertices": [[33000, 20000], [30000, 23000], [27000, 20000]],
            "arcs": [{"at": 0, "center": [30000, 20000], "radius": 3000},
                     {"at": 1, "center": [30000, 20000], "radius": 3000},
                     {"at": 2, "center": [30000, 20000], "radius": 3000}]}
    validator.validate(_with_core(ring))


def test_core_point_fallback_valid(validator):
    """core 不给，只用 core_anchor_mm → 通过（向后兼容）。"""
    p = _plan()
    p["zones"][0]["core_anchor_mm"] = [30000, 20000]
    validator.validate(p)


def test_core_and_legacy_coexist_valid(validator):
    """core ring + core_anchor_mm 共存 → 通过。"""
    p = _with_core([[27000,16000],[33000,16000],[33000,24000],[27000,24000]])
    p["zones"][0]["core_anchor_mm"] = [30000, 20000]
    validator.validate(p)


def test_core_bad_type_rejected(validator):
    """core = 字符串 → 拦。"""
    with pytest.raises(ValidationError):
        validator.validate(_with_core("not a shape"))
