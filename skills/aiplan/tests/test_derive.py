"""derive 派生事实层测试（P0 迁移，migration_to_v3_dsl.md §六 P0）。

验收：
- 矩形地块 → aspect_ratio / exposure_m / deep_zone_ratio 正确
- 带退线 → buildable_area 正确缩小、exposure 反映退线后边长
- L 形地块 → concave_corners > 0
- 主边方向判定（EW vs NS）
- 无退线 → buildable = lot
"""

from aiplan_tools.derive import derive_facts


# ── 正例：矩形地块（海湾精品酒店 80×60m，南退 8 其余 5）──────────────

def test_rect_lot_aspect_ratio():
    """80×60m 矩形 → aspect_ratio = 1.333。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    assert facts["aspect_ratio"] == 1.333
    assert facts["bounding_box_mm"]["w"] == 80000
    assert facts["bounding_box_mm"]["d"] == 60000


def test_rect_lot_area():
    """80×60m → lot_area = 4800㎡。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    assert facts["lot_area_sqm"] == 4800.0


def test_rect_lot_no_setbacks_buildable_equals_lot():
    """无退线 → buildable = lot。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    assert facts["buildable_area_sqm"] == 4800.0
    assert facts["buildable_ratio"] == 1.0


def test_rect_lot_with_setbacks_buildable_shrinks():
    """80×60m + 退线(南8/北5/东西5) → 可建 70×47=3290㎡。"""
    facts = derive_facts(
        [[0, 0], [80000, 0], [80000, 60000], [0, 60000]],
        {"front": 5000, "rear": 8000, "left": 5000, "right": 5000},
    )
    assert facts["buildable_area_sqm"] == 3290.0
    assert facts["buildable_ratio"] == 0.6854


def test_rect_lot_exposure_south_with_setbacks():
    """退线后南向可建边 = 70m（东西各退 5m → 80-5-5=70）。"""
    facts = derive_facts(
        [[0, 0], [80000, 0], [80000, 60000], [0, 60000]],
        {"front": 5000, "rear": 8000, "left": 5000, "right": 5000},
    )
    assert facts["exposure_m"]["S"] == 70.0
    assert facts["exposure_m"]["N"] == 70.0
    assert facts["exposure_m"]["E"] == 47.0  # 60-8-5=47
    assert facts["exposure_m"]["W"] == 47.0


def test_rect_lot_dominant_axes_ew():
    """宽(80) > 深(60) → 主边东西（EW）。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    assert facts["dominant_axes"] == "EW"


def test_rect_lot_dominant_axes_ns():
    """深(60) > 宽(40) → 主边南北（NS）。"""
    facts = derive_facts([[0, 0], [40000, 0], [40000, 60000], [0, 60000]])
    assert facts["dominant_axes"] == "NS"


def test_rect_lot_concave_zero():
    """矩形 → 凹角数 = 0。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    assert facts["concave_corners"] == 0


def test_rect_lot_deep_zone_ratio():
    """80×60m + 退线 → 暗区占比 > 0（有大片内部暗区）。"""
    facts = derive_facts(
        [[0, 0], [80000, 0], [80000, 60000], [0, 60000]],
        {"front": 5000, "rear": 8000, "left": 5000, "right": 5000},
    )
    assert 0 < facts["deep_zone_ratio"] < 1


# ── 正例：L 形地块 ──────────────────────────────────────────────

def test_l_shape_lot_concave_corner():
    """L 形地块 → 凹角数 ≥ 1。"""
    # L 形：缺右上角
    l_shape = [[0, 0], [80000, 0], [80000, 30000], [40000, 30000], [40000, 60000], [0, 60000]]
    facts = derive_facts(l_shape)
    assert facts["concave_corners"] >= 1


# ── 正例：方形地块 ──────────────────────────────────────────────

def test_square_lot_aspect_ratio_one():
    """60×60m 方形 → aspect_ratio = 1.0。"""
    facts = derive_facts([[0, 0], [60000, 0], [60000, 60000], [0, 60000]])
    assert facts["aspect_ratio"] == 1.0


# ── 反例/边界 ──────────────────────────────────────────────────

def test_degenerate_lot_no_crash():
    """退化输入（3 点共线）不崩溃，返回有效结构。"""
    facts = derive_facts([[0, 0], [80000, 0], [40000, 0]])
    assert "aspect_ratio" in facts
    assert "exposure_m" in facts


def test_partial_setbacks_only_front():
    """只给 front 退线，其余缺省 0。"""
    facts = derive_facts(
        [[0, 0], [80000, 0], [80000, 60000], [0, 60000]],
        {"front": 5000},
    )
    # 只北退 5 → 可建 80×55
    assert facts["buildable_area_sqm"] == 4400.0


# ── 结构完整性 ──────────────────────────────────────────────────

def test_facts_has_all_keys():
    """产出事实包含所有约定的键。"""
    facts = derive_facts([[0, 0], [80000, 0], [80000, 60000], [0, 60000]])
    expected_keys = {
        "aspect_ratio", "bounding_box_mm", "lot_area_sqm",
        "buildable_area_sqm", "buildable_ratio", "exposure_m",
        "deep_zone_ratio", "dominant_axes", "concave_corners",
    }
    assert set(facts.keys()) == expected_keys
    assert set(facts["exposure_m"].keys()) == {"N", "S", "E", "W"}
    assert set(facts["bounding_box_mm"].keys()) == {"w", "d", "minx", "miny", "maxx", "maxy"}
