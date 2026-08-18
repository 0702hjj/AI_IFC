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


# ---------------------------------------------------------------------------
# 波次 2（D40）：分层外推——差集/切割线/切段/认领
# ---------------------------------------------------------------------------

def _layered_skeleton_doc(**overrides):
    """分层外推夹具：30×30m outline + 20×20m corridor 外缘 + 10×10m core 居中。

    corridor zone = 20×20 − 10×10（环带）；大区 = 30×30 − 20×20（外环）。
    """
    doc = {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
        "zones": [{
            "zone": "tower",
            "axis_grid": {"x": [], "y": []},
            "outline": [
                {"outer": {"vertices": [[0, 0], [30000, 0], [30000, 30000], [0, 30000]]}}
            ],
            "core": {"anchor": [15000, 15000],
                     "vertices": [[10000, 10000], [20000, 10000], [20000, 20000], [10000, 20000]]},
            "corridor": {
                "form": "path", "width_mm": 5000,
                "path": {
                    "edges": {
                        "west": [[5000, 5000], [5000, 25000]],
                        "north": [[5000, 25000], [25000, 25000]],
                        "east": [[25000, 25000], [25000, 5000]],
                        "south": [[25000, 5000], [5000, 5000]],
                    },
                },
            },
            "main_partitions": [],
            "typology": "环形办公",
            "typology_reason": "core 居中",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        }],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestNormalizeLayeredPush:
    """D40：分层外推——corridor 差集 / 大区差集 / 切割切段 / blocks 认领。"""

    def test_corridor_zone_difference(self):
        """corridor zone = 外缘 − union(cores)（环带）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        cz = z["corridor_zone"]
        assert cz["polygon_mm"]["area_sqm"] == pytest.approx(300.0)  # 20×20 − 10×10 = 300㎡

    def test_big_zones_difference(self):
        """大区 = outline − corridor zone（外环 30×30 − 20×20 = 500㎡）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        bz = z["big_zones"]
        total = sum(b["polygon_mm"]["area_sqm"] for b in bz)
        assert total == pytest.approx(500.0)

    def test_cut_lines_anchored(self):
        """切割线 from/to 锚定 → 绝对坐标线段。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        cuts = {c["id"]: c for c in z["cuts"]}
        # cut:0 竖线：corridor N 边中点 (15000,25000) → outline N 边中点 (15000,30000)
        assert cuts["cut:0"]["line_mm"][0] == pytest.approx([15000.0, 25000.0])
        assert cuts["cut:0"]["line_mm"][1] == pytest.approx([15000.0, 30000.0])

    def test_segments_split_and_blocks_between(self):
        """2 条径向切割 → 大区切 2 段；blocks between + side 认领。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        doc["zones"][0]["blocks"] = [
            {"id": "b_east", "role": "open_office", "between": ["cut:0", "cut:1"], "side": "E"},
            {"id": "b_west", "role": "units", "between": ["cut:0", "cut:1"], "side": "W"},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        blocks = {b["id"]: b for b in z["blocks"]}
        assert len(z["cuts"]) == 2
        # 东西两块各约 250㎡（外环 500㎡ 对半）
        assert blocks["b_east"]["polygon_mm"]["area_sqm"] == pytest.approx(250.0, abs=1.0)
        assert blocks["b_west"]["polygon_mm"]["area_sqm"] == pytest.approx(250.0, abs=1.0)
        # 认领的段在正确侧：东块质心 x > 15000
        east_centroid = blocks["b_east"]["polygon_mm"]["centroid_mm"]
        assert east_centroid[0] > 15000

    def test_axis_grid_derived(self):
        """轴网派生：分区边界坐标集合（模型不手填）。"""
        m = normalize_skeleton(_layered_skeleton_doc())
        z = m["zones"][0]
        ag = z["axis_grid_derived"]
        # 无切割线场景：边界坐标 = outline/corridor/core 的顶点
        assert ag["x"] == [0.0, 5000.0, 10000.0, 20000.0, 25000.0, 30000.0]
        assert ag["y"] == [0.0, 5000.0, 10000.0, 20000.0, 25000.0, 30000.0]

    def test_partition_labels(self):
        """分区标签：段质心 BLOCK_<id>。"""
        doc = _layered_skeleton_doc()
        doc["zones"][0]["main_partitions"] = [
            {"id": "cut:0", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "N", "at": 0.5},
             "to": {"ref": "outline:edge:2", "at": 0.5}},
            {"id": "cut:1", "role": "radial",
             "from": {"ref": "corridor:outer", "edge": "S", "at": 0.5},
             "to": {"ref": "outline:edge:0", "at": 0.5}},
        ]
        doc["zones"][0]["blocks"] = [
            {"id": "b_east", "role": "open_office", "between": ["cut:0", "cut:1"], "side": "E"},
        ]
        m = normalize_skeleton(doc)
        z = m["zones"][0]
        labels = {l["block"]: l for l in z["partition_labels"]}
        assert "b_east" in labels
        lab = labels["b_east"]
        assert lab["tag"] == "BLOCK_b_east"
        assert lab["at_mm"][0] > 15000  # 东块质心


# ---------------------------------------------------------------------------
# 波次 3（D41）：rooms 直接声明墙——walls 解析/墙围区域/opening 挂墙
# ---------------------------------------------------------------------------

def _wall_rooms_skeleton():
    """形态族 D 夹具：12×6m outline（无 core/corridor）——rooms 在轮廓内画分墙。"""
    return {
        "frame": {"units": "mm", "origin": "lot_southwest", "north_deg": 0, "modulus": 100},
        "zones": [{
            "zone": "house",
            "axis_grid": {"x": [], "y": []},
            "outline": [
                {"outer": {"vertices": [[0, 0], [12000, 0], [12000, 6000], [0, 6000]]}}
            ],
            "typology": "独立块",
            "typology_reason": "single family",
            "note_responses": [],
            "deviations": [],
            "defaults_used": [],
        }],
    }


def _wall_rooms_doc(**overrides):
    """rooms：两道竖分墙 + 三个标签（三开间）+ 门挂墙。"""
    doc = {
        "floor": "house",
        "zone_ref": "skeleton.json#zones[house]",
        "partitions": {"main": "outline"},
        "walls": [
            {"key": "1F:int:0", "kind": "int", "t_mm": 120,
             "axis": [[4000, 0], [4000, 6000]]},
            {"key": "1F:int:1", "kind": "int", "t_mm": 120,
             "axis": [[8000, 0], [8000, 6000]]},
        ],
        "labels": [
            {"room": "bedroom_01", "type": "bedroom", "area_sqm": 24, "at": [2000, 3000]},
            {"room": "living_01", "type": "living", "area_sqm": 24, "at": [6000, 3000]},
            {"room": "bedroom_02", "type": "bedroom", "area_sqm": 24, "at": [10000, 3000]},
        ],
        "openings": [
            {"wall": "1F:int:0", "along_m": 2.0, "w_mm": 900, "type": "door"},
            {"wall": "1F:int:1", "along_m": 3.0, "w_mm": 900, "type": "door"},
        ],
        "requirements_trace": [],
        "deviations": [],
        "defaults_used": [],
    }
    for k, v in overrides.items():
        doc[k] = v
    return doc


class TestNormalizeRoomsWalls:
    """D41：rooms walls 解析 + 墙围区域 + opening 挂墙。"""

    def test_walls_parse_absolute(self):
        """walls axis（绝对坐标）→ 墙轴线线段。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        walls = {w["key"]: w for w in m["walls"]}
        assert walls["1F:int:0"]["line_mm"] == [[4000.0, 0.0], [4000.0, 6000.0]]

    def test_rooms_regions_polygonized(self):
        """墙 + 轮廓边 → 围出 3 区域；labels at 落区绑定。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        rooms = {r["room"]: r for r in m["rooms"]}
        assert set(rooms) == {"bedroom_01", "living_01", "bedroom_02"}
        # 三开间各 4×6 = 24㎡
        assert rooms["bedroom_01"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)
        assert rooms["living_01"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)

    def test_opening_along_wall(self):
        """opening 挂墙 key + along → 沿墙绝对位置。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        m = normalize_rooms(_wall_rooms_doc(), skel)
        opens = {o["type"] + str(i): o for i, o in enumerate(m["openings"])}
        o0 = m["openings"][0]
        assert o0["wall_key"] == "1F:int:0"
        # along 2m 沿墙起点 [4000,0] → [4000, 2000]
        assert o0["at_mm"] == pytest.approx([4000.0, 2000.0])

    def test_opening_wall_key_invalid(self):
        """opening 挂不存在的墙 key → SchemaError。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        doc = _wall_rooms_doc()
        doc["openings"] = [{"wall": "1F:nope:9", "along_m": 2.0, "w_mm": 900, "type": "door"}]
        with pytest.raises(SchemaError):
            normalize_rooms(doc, skel)

    def test_axis_grid_path_wall(self):
        """axis-grid path 索引粗轴网 → 折线分墙。"""
        skel = normalize_skeleton(_wall_rooms_skeleton())
        skel["zones"][0]["axis_grid_derived"] = {"x": [0, 4000, 8000, 12000],
                                                 "y": [0, 3000, 6000]}
        doc = _wall_rooms_doc()
        doc["walls"] = [
            {"key": "1F:int:0", "kind": "int", "t_mm": 120,
             "path": [{"x": 1, "y": 0}, {"x": 1, "y": 2}]},   # x=4000 竖墙（0→6000）
        ]
        doc["labels"] = [
            {"room": "a", "type": "living", "area_sqm": 24, "at": [2000, 3000]},
            {"room": "b", "type": "living", "area_sqm": 48, "at": [8000, 3000]},
        ]
        doc["openings"] = []
        m = normalize_rooms(doc, skel)
        walls = {w["key"]: w for w in m["walls"]}
        assert walls["1F:int:0"]["line_mm"] == [[4000.0, 0.0], [4000.0, 6000.0]]
        rooms = {r["room"]: r for r in m["rooms"]}
        assert rooms["a"]["polygon_mm"]["area_sqm"] == pytest.approx(24.0)
        assert rooms["b"]["polygon_mm"]["area_sqm"] == pytest.approx(48.0)
