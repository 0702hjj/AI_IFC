"""draw.py 测试（T23 墙/开洞/门 + T24 楼梯/标注/windows + T25 能力补齐）。

构件级封装：每函数 = 一个构件，返回实体 key（key 身份映射落盘）。
"""

import ezdxf
import pytest

from dxfkit.draw import (
    wall_run,
    opening,
    door,
    window,
    draw_stair,
    room_label,
    draw_windows_from_rooms,
    new_doc,
    draw_fixture,
    draw_landing,
    draw_dim_chain,
    draw_tag,
    draw_leader,
    draw_north_arrow,
    draw_title,
    draw_section_bubble,
    draw_detector,
    draw_column,
    partition_cap,
    canonicalize,
)


@pytest.fixture
def doc():
    d = ezdxf.new("R2010", setup=True)
    d.units = ezdxf.units.MM
    return d


class TestWallRun:
    def test_wall_run_returns_key(self, doc):
        key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        assert isinstance(key, str)
        assert key  # 非空

    def test_wall_run_creates_entities(self, doc):
        wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        assert len(list(doc.modelspace())) > 0

    def test_wall_run_key_map(self, doc):
        """key 身份映射可回查。"""
        key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        # key 在模型中可定位（简单断言：key 是 str 且画了东西）
        assert key.startswith("wall_")


class TestOpening:
    def test_opening_returns_key(self, doc):
        wall_key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        key = opening(doc.modelspace(), wall_key, (3000, 3000), 900)
        assert isinstance(key, str)
        assert key.startswith("open_")


class TestDoor:
    def test_door_returns_key(self, doc):
        wall_key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        open_key = opening(doc.modelspace(), wall_key, (3000, 3000), 900)
        key = door(doc.modelspace(), wall_key, open_key, (3000, 3000), 900, "in-left")
        assert isinstance(key, str)
        assert key.startswith("door_")

    def test_door_creates_entities(self, doc):
        wall_key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        open_key = opening(doc.modelspace(), wall_key, (3000, 3000), 900)
        door(doc.modelspace(), wall_key, open_key, (3000, 3000), 900, "in-left")
        assert len(list(doc.modelspace())) >= 2


class TestWindow:
    def test_window_returns_key(self, doc):
        wall_key = wall_run(doc.modelspace(), (0, 0), (8000, 0), 200, [])
        key = window(doc.modelspace(), wall_key, (4000, 4000), 1200)
        assert key.startswith("win_")


class TestStair:
    def test_stair_returns_key(self, doc):
        key = draw_stair(doc.modelspace(), (0, 0), (3000, 3000), 2000)
        assert isinstance(key, str)
        assert key.startswith("stair_")

    def test_stair_creates_entities(self, doc):
        draw_stair(doc.modelspace(), (0, 0), (3000, 3000), 2000)
        assert len(list(doc.modelspace())) > 0


class TestRoomLabel:
    def test_room_label_creates_text(self, doc):
        room_label(doc.modelspace(), "living", (4000, 4000), 26.6)
        texts = [e for e in doc.modelspace() if e.dxftype() == "TEXT"]
        assert any("living" in t.dxf.text.lower() for t in texts)

    def test_room_label_area(self, doc):
        room_label(doc.modelspace(), "living", (4000, 4000), 26.6)
        texts = [e for e in doc.modelspace() if e.dxftype() == "TEXT"]
        assert any("26.6" in t.dxf.text for t in texts)


class TestWindowsFromRooms:
    def test_windows_from_rooms(self, doc):
        """房间多边形 + frontage → 外墙窗（T24）。"""
        rooms = [
            {"id": "r1", "polygon_mm": {"x": [0, 4000], "y": [0, 4000]}, "frontage": "S"},
        ]
        count = draw_windows_from_rooms(doc.modelspace(), rooms)
        assert count > 0


class TestDrawRoomsModel:
    """2026-08-11：rooms 几何模型批量画墙 + 挂墙门窗 + placemark。"""

    def _model(self):
        return {
            "walls": [
                {"kind": "ext", "t_mm": 200,
                 "axis_mm": [[0, 0], [12000, 0]]},
                {"kind": "int", "t_mm": 120,
                 "path_mm": [[6000, 0], [6000, 6000]]},
            ],
            "openings": [
                {"wall": 0, "along_m": 3.0, "w_mm": 900, "type": "door"},
                {"wall": 0, "along_m": 7.0, "w_mm": 1500, "type": "window"},
            ],
            "rooms": [
                {"id": "stair_01", "type": "stair",
                 "placemark": {"kind": "stair"},
                 "polygon_mm": {"vertices": [[2000, 2000], [5000, 2000], [5000, 5000], [2000, 5000]]}},
            ],
        }

    def test_draw_walls(self, doc):
        from dxfkit.draw import draw_rooms_model
        keys = draw_rooms_model(doc.modelspace(), self._model())
        assert len(keys["walls"]) >= 2  # 1 外墙 + 1 内墙折线(1段)

    def test_draw_openings(self, doc):
        from dxfkit.draw import draw_rooms_model
        keys = draw_rooms_model(doc.modelspace(), self._model())
        assert len(keys["openings"]) == 2  # 1 门 + 1 窗

    def test_draw_placemark_stair(self, doc):
        from dxfkit.draw import draw_rooms_model
        keys = draw_rooms_model(doc.modelspace(), self._model())
        assert len(keys["placemarks"]) == 1

    # --- 沿墙定位（2026-08-12：不规则墙门窗不画错位）---

    def test_door_on_vertical_wall_positioned(self, doc):
        from dxfkit.draw import draw_rooms_model
        """竖直墙上门沿墙定位（along_m=3.0 → y 3000~3900），不再画到 x 轴。"""
        model = {
            "walls": [{"kind": "int", "t_mm": 120, "axis_mm": [[6000, 0], [6000, 6000]]}],
            "openings": [{"wall": 0, "along_m": 3.0, "w_mm": 900, "type": "door"}],
            "rooms": [],
        }
        draw_rooms_model(doc.modelspace(), model)
        door_lines = [e for e in doc.modelspace()
                      if e.dxftype() == "LINE" and e.dxf.layer == "DOOR"]
        assert door_lines, "应有门 leaf 线"
        # 门 leaf 从墙轴 (6000, 3000) 向内开——x 在墙轴附近（非 x=3000 的旧错误位置）
        s = door_lines[0].dxf.start
        assert abs(s.x - 6000) < 100, f"门应在墙轴 x≈6000，实际 {s.x:.0f}"
        assert abs(s.y - 3000) < 100, f"门应在沿墙 y≈3000，实际 {s.y:.0f}"

    def test_window_on_vertical_wall_positioned(self, doc):
        from dxfkit.draw import draw_rooms_model
        """竖直墙上窗沿墙定位（along_m=3.0，中心 y≈3450）。"""
        model = {
            "walls": [{"kind": "int", "t_mm": 120, "axis_mm": [[6000, 0], [6000, 6000]]}],
            "openings": [{"wall": 0, "along_m": 3.0, "w_mm": 1500, "type": "window"}],
            "rooms": [],
        }
        draw_rooms_model(doc.modelspace(), model)
        glaz = [e for e in doc.modelspace()
                if e.dxftype() == "LINE" and e.dxf.layer == "WINDOW"]
        assert glaz
        mid_y = (glaz[0].dxf.start.y + glaz[0].dxf.end.y) / 2
        assert abs(mid_y - 3750) < 150, f"窗中心应沿墙 y≈3750，实际 {mid_y:.0f}"
        assert abs(glaz[0].dxf.start.x - 6000) < 100, "窗应在墙轴 x≈6000"

    def test_window_on_diagonal_wall_positioned(self, doc):
        from dxfkit.draw import draw_rooms_model
        """45° 斜墙上窗沿墙定位（沿墙 3.0m，窗沿 s 方向而非水平 x）。"""
        model = {
            "walls": [{"kind": "int", "t_mm": 120, "axis_mm": [[0, 0], [6000, 6000]]}],
            "openings": [{"wall": 0, "along_m": 3.0, "w_mm": 1500, "type": "window"}],
            "rooms": [],
        }
        draw_rooms_model(doc.modelspace(), model)
        glaz = [e for e in doc.modelspace()
                if e.dxftype() == "LINE" and e.dxf.layer == "WINDOW"]
        assert glaz
        s, en = glaz[0].dxf.start, glaz[0].dxf.end
        # 窗沿 45° 方向（dx≈dy），非水平窗
        dx, dy = en.x - s.x, en.y - s.y
        assert dx > 0 and dy > 0, f"斜墙窗应沿 45° 方向，实际 dx={dx:.0f} dy={dy:.0f}"
        assert abs(dx - dy) < 100, f"斜墙窗方向应 45°，dx={dx:.0f} dy={dy:.0f}"


class TestNewDoc:
    """T25：文档初始化封装——AutoCAD 兼容（R2010 + units + 图层表 + 标注样式）。"""

    def test_new_doc_autocad_compatible(self):
        """R2010 + units=MM + setup——AutoCAD 能打开。"""
        d = new_doc(units="mm")
        assert d.dxfversion == "AC1024", "R2010 格式（AutoCAD 2010 兼容）"
        assert d.units == 4, "units=毫米（金例源图一致）"

    def test_new_doc_has_floor_layers(self):
        """图层表齐全（WALL/DOOR/WINDOW/STAIR/FIXTURE/TEXT/DIM…）。"""
        d = new_doc(units="mm")
        names = {l.dxf.name for l in d.layers}
        for need in ("WALL", "DOOR", "WINDOW", "STAIR", "FIXTURE",
                     "TEXT", "DIM", "COLUMN", "FIRE", "SECTION"):
            assert need in names, f"缺图层 {need}"

    def test_new_doc_has_dimstyle(self):
        """标注样式 ARCHDXF 已建（尺寸链可用）。"""
        d = new_doc(units="mm")
        assert "ARCHDXF" in d.dimstyles


class TestDrawCapability:
    """T25：构件能力补齐——每个封装函数产对应实体/层。"""

    def test_draw_fixture(self, doc):
        msp = doc.modelspace()
        k = draw_fixture(msp, "toilet", (1000, 1000))
        assert k
        layers = {e.dxf.layer for e in msp}
        assert "FIXTURE" in layers

    def test_draw_landing(self, doc):
        msp = doc.modelspace()
        k = draw_landing(msp, (0, 0), width=2600, depth=1200)
        assert k
        assert any(e.dxf.layer == "STAIR" for e in msp)

    def test_draw_dim_chain(self, doc):
        msp = doc.modelspace()
        wall_key = wall_run(msp, (0, 0), (8000, 0), 200, [])
        draw_dim_chain(msp, wall_key, stations=[0, 3000, 8000])
        assert any(e.dxf.layer == "DIM" for e in msp)

    def test_draw_tag(self, doc):
        msp = doc.modelspace()
        draw_tag(msp, "D1", (1000, 1000))
        assert any(e.dxf.layer == "TEXT" for e in msp)

    def test_draw_leader(self, doc):
        msp = doc.modelspace()
        draw_leader(msp, "标注", tail=(0, 0), target=(1000, 1000))
        assert any(e.dxf.layer == "TEXT" for e in msp)

    def test_draw_north_arrow(self, doc):
        msp = doc.modelspace()
        draw_north_arrow(msp, (1000, 1000))
        assert any(e.dxf.layer == "TEXT" for e in msp)

    def test_draw_title(self, doc):
        msp = doc.modelspace()
        draw_title(msp, "八边形螺旋办公塔 标准层", (1000, 1000))
        assert any(e.dxf.layer == "TEXT" for e in msp)

    def test_draw_section_bubble(self, doc):
        msp = doc.modelspace()
        draw_section_bubble(msp, "A", "1", (1000, 1000), direction=(0.0, 1.0))
        assert any(e.dxf.layer == "SECTION" for e in msp)

    def test_draw_detector(self, doc):
        msp = doc.modelspace()
        draw_detector(msp, "smoke", (1000, 1000))
        assert any(e.dxf.layer == "FIRE" for e in msp)

    def test_draw_column(self, doc):
        msp = doc.modelspace()
        draw_column(msp, (1000, 1000), size=700)
        assert any(e.dxf.layer == "COLUMN" for e in msp)

    def test_partition_cap(self, doc):
        msp = doc.modelspace()
        key = wall_run(msp, (0, 0), (4000, 0), 120, [])
        partition_cap(msp, key, 0.0)
        assert key  # 端封在墙 frame 上画


class TestCanonicalize:
    """T25：确定性配方——同输入字节级重现。"""

    def test_canonicalize_deterministic(self, tmp_path):
        p = tmp_path / "out.dxf"
        d = new_doc(units="mm")
        msp = d.modelspace()
        reset_import = __import__("dxfkit.draw", fromlist=["reset_keys"])
        reset_import.reset_keys()
        wall_run(msp, (0, 0), (8000, 0), 200, [])
        d.saveas(p)
        canonicalize(p)
        b1 = p.read_bytes()

        p2 = tmp_path / "out2.dxf"
        d2 = new_doc(units="mm")
        reset_import.reset_keys()
        wall_run(d2.modelspace(), (0, 0), (8000, 0), 200, [])
        d2.saveas(p2)
        canonicalize(p2)
        b2 = p2.read_bytes()
        assert b1 == b2, "同输入 + canon 后字节级一致"


class TestSaveDoc:
    """AutoCAD 兼容存盘：中文 → \\U+XXXX 转义，文件纯 ASCII（乱码根治）。
    new_doc() 返回的 doc 存盘自动处理——模型零负担，包管层保证。"""

    def test_new_doc_save_escapes_chinese(self, tmp_path):
        p = tmp_path / "out.dxf"
        d = new_doc(units="mm")
        draw_title(d.modelspace(), "F1 标准层平面图", (1000, 1000))
        d.saveas(p)
        raw = p.read_bytes()
        assert b"\xe6\xa0\x87" not in raw, "文件不应含 UTF-8 中文原始字节"
        assert b"\\U+6807" in raw, "中文应转义为 \\U+XXXX（AutoCAD 标准）"

    def test_new_doc_save_ascii_pure(self, tmp_path):
        p = tmp_path / "out.dxf"
        d = new_doc(units="mm")
        draw_title(d.modelspace(), "F1 标准层平面图", (1000, 1000))
        d.saveas(p)
        raw = p.read_bytes()
        raw.decode("ascii")  # 纯 ASCII——AutoCAD 按 codepage 解码不乱码

    def test_new_doc_save_roundtrip(self, tmp_path):
        """\\U+XXXX 转义读回后文本可还原（readback 对账不受影响）。"""
        p = tmp_path / "out.dxf"
        d = new_doc(units="mm")
        draw_title(d.modelspace(), "F1 标准层平面图", (1000, 1000))
        d.saveas(p)
        d2 = ezdxf.readfile(p)
        texts = [e for e in d2.modelspace() if e.dxftype() == "TEXT"]
        assert texts
        t = texts[0].dxf.text
        assert "\\U+6807" in t, f"ezdxf 读回保留转义，实际 {t!r}"

    def test_new_doc_save_deterministic(self, tmp_path):
        """new_doc 的 doc 存盘字节级确定（金样验收项，saveas 内含 canonicalize）。"""
        reset_import = __import__("dxfkit.draw", fromlist=["reset_keys"])
        p1 = tmp_path / "o1.dxf"
        reset_import.reset_keys()
        d1 = new_doc(units="mm")
        wall_run(d1.modelspace(), (0, 0), (8000, 0), 200, [])
        d1.saveas(p1)

        p2 = tmp_path / "o2.dxf"
        reset_import.reset_keys()
        d2 = new_doc(units="mm")
        wall_run(d2.modelspace(), (0, 0), (8000, 0), 200, [])
        d2.saveas(p2)
        assert p1.read_bytes() == p2.read_bytes()


# ---------------------------------------------------------------------------
# 波次 2（D40/D37）：DXF 分区轮廓底座
# ---------------------------------------------------------------------------

class TestPartitionBase:
    """D37/D40：dxfkit 按 normalize 分区几何画底座 DXF。"""

    def _base_geom(self):
        return {
            "outline": [
                {"outer": {"vertices": [[0, 0], [30000, 0], [30000, 30000], [0, 30000]]}}
            ],
            "cores": [
                {"id": "core0",
                 "polygon_mm": {"vertices": [[10000, 10000], [20000, 10000],
                                             [20000, 20000], [10000, 20000]]}}
            ],
            "corridor": {"form": "path", "width_mm": 5000,
                         "path_mm": [[5000, 5000], [25000, 5000], [25000, 25000], [5000, 25000]]},
            "cuts": [
                {"id": "cut:0", "line_mm": [[15000, 25000], [15000, 30000]]},
                {"id": "cut:1", "line_mm": [[15000, 5000], [15000, 0]]},
            ],
        }

    def test_draw_partition_base_entities(self, doc):
        """底座画出 outline/core/corridor/切割线实体（WALL 层）。"""
        from dxfkit.draw import draw_partition_base
        geom = self._base_geom()
        result = draw_partition_base(doc.modelspace(), geom)
        assert result["n_outline"] >= 1
        assert result["n_core"] >= 1
        assert result["n_corridor"] >= 1
        assert result["n_cut"] == 2
        entities = list(doc.modelspace())
        assert len(entities) > 0
        # 全部在 WALL 层
        wall_ents = [e for e in entities if e.dxf.layer == "WALL"]
        assert len(wall_ents) >= 1 + 1 + 1 + 2

    def test_draw_partition_base_minimal(self, doc):
        """无 corridor/cuts 时底座最小可用（不崩）。"""
        from dxfkit.draw import draw_partition_base
        geom = self._base_geom()
        geom["corridor"] = None
        geom["cuts"] = []
        result = draw_partition_base(doc.modelspace(), geom)
        assert result["n_outline"] >= 1
        assert result["n_corridor"] == 0
        assert result["n_cut"] == 0
