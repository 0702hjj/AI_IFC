"""normalize path/ring_edges 测试（多段 path + D39 分段协议）。

拆分自 test_normalize.py（W-0049 文件行数门控），夹具复用 test_normalize。
"""

import pytest

from floorgeom.normalize import SchemaError, normalize_skeleton, normalize_rooms
from test_normalize import _skeleton_doc  # noqa: F401


# ---------------------------------------------------------------------------
# T14 rooms 半
# ---------------------------------------------------------------------------

def _rooms_skeleton() -> dict:
    """rooms 测试用的骨架几何模型（normalize_skeleton 产出）。"""
    return normalize_skeleton(_skeleton_doc())


def _rooms_doc(**overrides):
    doc = {
        "floor": "podium_1f",
        "axis_grid_ref": "skeleton.json#zones[podium].axis_grid",
        "rooms": [
            {"id": "shop_01", "type": "shop", "area_sqm": 80,
             "loc": {"between_axes": {"x": [0, 2], "y": [0, 2]}}},
        ],
        "openings": [],
        "requirements_trace": [],
        "deviations": [],
        "defaults_used": [],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


def _ring_edges_doc(**overrides):
    """最小 ring_edges（4 边拼合 24m×24m 矩形）。"""
    ring = {
        "edges": {
            "west": [[6000, 6000], [6000, 18000]],
            "north": [[6000, 18000], [18000, 18000]],
            "east": [[18000, 18000], [18000, 6000]],
            "south": [[18000, 6000], [6000, 6000]],
        },
    }
    ring.update(overrides)
    return ring


class TestMultiSegmentPath:
    """2026-08-11：多段 path 兼容性——用户强调的核心能力。"""






    def test_core_vertices_inherited(self):
        """core vertices 形式（D36：绝对坐标 ring 继承 plan core——非轴网对齐核心筒）。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = {
            "anchor": [9281, 9365],
            "vertices": {"vertices": [[10951, 5240], [8001, 5240], [8001, 8464],
                                      [6230, 8464], [6230, 12342], [12170, 12342],
                                      [12170, 8464], [10951, 8464]]},  # 凸字形，非轴网交点
        }
        m = normalize_skeleton(doc)
        poly = m["zones"][0]["core"]["polygon_mm"]
        assert "vertices" in poly
        assert len(poly["vertices"]) == 8
        assert poly["vertices"][0] == [10951.0, 5240.0]  # 绝对坐标原样（不经轴网解析）

    def test_core_vertices_with_arc(self):
        """core vertices ring 带 arcAnn（绝对坐标弧）→ 离散。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = {
            "anchor": [9281, 9365],
            "vertices": {"vertices": [[0, 0], [10000, 0], [10000, 10000], [0, 10000]],
                         "arcs": [{"at": 0, "center": [5000, 0], "radius": 5000,
                                   "a0": 180, "a1": 360}]},
        }
        m = normalize_skeleton(doc)
        poly = m["zones"][0]["core"]["polygon_mm"]
        assert len(poly["vertices"]) > 4, "弧边离散后顶点应多于直边"


    def test_holes_resolve_polygon(self):
        """holes ring → normalize 产出多边形。"""
        doc = _skeleton_doc()
        doc["zones"][0]["holes"] = [
            {"vertices": [[20000, 15000], [28000, 15000], [28000, 22000], [20000, 22000]]}
        ]
        m = normalize_skeleton(doc)
        holes = m["zones"][0]["holes"]
        assert isinstance(holes, list) and len(holes) == 1
        assert "polygon_mm" in holes[0]
        assert len(holes[0]["polygon_mm"]["vertices"]) >= 4




    def test_ring_edges_basic_polygon(self):
        """四边拼合 → 闭合顶点（去重复角点）。"""
        from floorgeom.normalize import _edges_to_base
        base = _edges_to_base(_ring_edges_doc()["edges"])
        assert base[0] == [6000, 6000]           # 西南角（west 起点）
        assert base[-1] == [18000, 6000]         # 东南角（south 末点）
        assert len(base) == 4                    # 4 角矩形：4 顶点
        assert base[1] == [6000, 18000]          # 西北角

    def test_ring_edges_recess_expand(self):
        """recess 凹进展开（W 边 offset 6m 宽 6m 深 1.5m）。"""
        from floorgeom.normalize import _expand_ring_edges
        ring = _ring_edges_doc(segments=[
            {"type": "recess", "at_edge": "W", "offset_m": 6.0,
             "width_m": 6.0, "depth_m": 1.5},
        ])
        out = _expand_ring_edges(ring, is_outer=True)
        pts = out["vertices"]
        # 凹进 4 点（a, a2, b2, b）：顶点数 4 → 8
        assert len(pts) == 8
        # 凹进深度 1.5m：W 边 offset 6m 处向环内凹进（外法向为西 −x，
        # recess 向内 = −外法向 = +x）——凹进点 x = 6000+1500 = 7500
        deep_pts = [p for p in pts if p[0] == pytest.approx(7500.0, abs=1e-6)]
        assert len(deep_pts) == 2  # a2=(7500,12000) + b2=(7500,6000)

    def test_ring_edges_same_edge_multiple(self):
        """同边多处凹凸（分组展开，从后往前防偏移）。"""
        from floorgeom.normalize import _expand_ring_edges
        ring = _ring_edges_doc(segments=[
            {"type": "recess", "at_edge": "W", "offset_m": 0.0,
             "width_m": 2.0, "depth_m": 1.0},
            {"type": "projection", "at_edge": "W", "offset_m": 8.0,
             "width_m": 3.0, "depth_m": 1.5},
        ])
        out = _expand_ring_edges(ring, is_outer=True)
        pts = out["vertices"]
        # 两处凹凸：4 顶点 → 12 顶点
        assert len(pts) == 12

    def test_ring_edges_arc_fillet(self):
        """at_vertex 圆角：顶点变 2 点 + arc 标注。"""
        from floorgeom.normalize import _expand_ring_edges
        ring = _ring_edges_doc(segments=[
            {"type": "arc", "at_vertex": 1, "radius_m": 2.0},
        ])
        out = _expand_ring_edges(ring, is_outer=True)
        pts = out["vertices"]
        assert len(pts) == 5          # 1 角倒圆：4 → 5（1 点变 2 点）
        assert len(out["arcs"]) == 1
        arc = out["arcs"][0]
        assert arc["radius"] == pytest.approx(2000.0)
        assert set(arc) >= {"at", "center", "radius", "a0", "a1"}

    def test_ring_edges_segment_exceeds_edge(self):
        """segment 超出边 → SchemaError。"""
        from floorgeom.normalize import _expand_ring_edges
        ring = _ring_edges_doc(segments=[
            {"type": "recess", "at_edge": "W", "offset_m": 20.0,
             "width_m": 6.0, "depth_m": 1.5},
        ])
        with pytest.raises(SchemaError):
            _expand_ring_edges(ring, is_outer=True)


class TestNormalizeSkeletonRingEdges:
    """D39：normalize_skeleton 消费 ring_edges（core/corridor path 分段）。"""

    def test_core_path_ring_edges(self):
        """core.path = ring_edges → polygon_mm 顶点。"""
        doc = _skeleton_doc()
        doc["zones"][0]["core"] = {"anchor": [12000, 12000],
                                   "path": _ring_edges_doc()}
        m = normalize_skeleton(doc)
        core = m["zones"][0]["core"]
        assert core["polygon_mm"]["vertices"][0] == pytest.approx([6000.0, 6000.0])

    def test_corridor_path_ring_edges(self):
        """corridor form=path + ring_edges（带 recess）→ 走廊线展开顶点。"""
        doc = _skeleton_doc()
        doc["zones"][0]["corridor"] = {
            "form": "path", "width_mm": 2400,
            "path": _ring_edges_doc(segments=[
                {"type": "recess", "at_edge": "W", "offset_m": 6.0,
                 "width_m": 6.0, "depth_m": 1.5},
            ]),
        }
        m = normalize_skeleton(doc)
        corr = m["zones"][0]["corridor"]
        assert corr is not None
        assert "path_mm" in corr
        assert len(corr["path_mm"]) == 8   # 4 角 + 4 凹进点


