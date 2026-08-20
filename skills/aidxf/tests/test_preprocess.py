"""preprocess.py 测试（T40 plan 校验+DAG / T41 zone 打包+vocab 裁剪 / D35 skeleton 底座）。"""

import json
from pathlib import Path

import pytest

from flowops.preprocess import (
    preprocess,
    derive_dag,
    merge_representative_floors,
    build_zone_pack,
    build_skeleton_base,
)

# 金样 plan：podium(1-2F) + tower(3-7F) 渐退
GOLD_PLAN = {
    "version": 3,
    "project": "示例商住楼",
    "site": {
        "lot_polygon_mm": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
        "origin": "lot_southwest", "north_deg": 0,
        "setbacks_mm": {"front": 6000, "rear": 4000, "left": 4000, "right": 4000},
    },
    "zones": [
        {
            "id": "podium", "function": "retail",
            "floors": {"from": 1, "to": 2}, "floor_height_mm": 4200,
            "outline_mm": [{"outer": [[0, 0], [60000, 0], [60000, 40000], [0, 40000]],
                            "holes": [], "arcs": []}],
            "program": [{"room": "shop", "count": 4, "area_sqm": [35, 55]}],
        },
        {
            "id": "tower", "function": "residence",
            "floors": {"from": 3, "to": 7}, "floor_height_mm": 3000,
            "outline_mm": [{"outer": [[18000, 22000], [42000, 22000], [42000, 40000], [18000, 40000]],
                            "holes": [], "arcs": []}],
            "position": {"on": "podium", "align": "north_center"},
            "program": [{"room": "unit_2br", "count": 2, "area_sqm": [62, 72]}],
        },
    ],
    "vertical_relations": [
        {"type": "core_continuous", "from": "tower", "through": "podium", "to_ground": True},
    ],
}


class TestDeriveDag:
    """T40-4：DAG 派生（vertical_relations → depends_on 边）。"""

    def test_dag_edges(self):
        """异楼层 zone 无画图依赖 → DAG 无边（顺序推进不依赖）。

        回归：position.on/vertical_relations 是几何/结构约束（塔楼⊆裙房投影、
        核筒跨层对齐 R-06），由 normalize 落位 + check 校验，不是画图顺序依赖——
        塔楼 rooms 不依赖裙房 rooms，可任意顺序处理（线性逐 zone）。
        """
        dag = derive_dag(GOLD_PLAN)
        assert "edges" in dag
        assert dag["edges"] == []

    def test_dag_node_floor_mapping(self):
        dag = derive_dag(GOLD_PLAN)
        # 节点带 covers（代表层）
        for node in dag.get("nodes", []):
            assert "covers" in node
            assert "floor" in node


class TestMergeRepresentativeFloors:
    """T40-3：楼层归并（同构标记 covers）。"""

    def test_podium_merges_1_2(self):
        merged = merge_representative_floors(GOLD_PLAN)
        podium = merged["podium"]
        assert podium["covers"] == ["f1", "f2"]
        assert podium["representative"] == "f1"

    def test_tower_merges_3_7(self):
        merged = merge_representative_floors(GOLD_PLAN)
        tower = merged["tower"]
        assert tower["covers"] == ["f3", "f4", "f5", "f6", "f7"]
        assert tower["representative"] == "f3"

    def test_zone_count(self):
        merged = merge_representative_floors(GOLD_PLAN)
        assert set(merged) == {"podium", "tower"}


class TestPreprocess:
    """T40 总装：plan → derived/floors.json + <zone>.json。"""

    def test_preprocess_outputs_floors_json(self, tmp_path):
        out = tmp_path / "derived"
        result = preprocess(GOLD_PLAN, str(out))
        floors_path = out / "floors.json"
        assert floors_path.exists()
        data = json.loads(floors_path.read_text(encoding="utf-8"))
        assert "dag" in data
        assert "zones" in data

    def test_preprocess_zone_packs(self, tmp_path):
        out = tmp_path / "derived"
        preprocess(GOLD_PLAN, str(out))
        # 每 zone 一包
        assert (out / "podium.json").exists()
        assert (out / "tower.json").exists()

    def test_preprocess_rejects_bad_outline(self, tmp_path):
        """轮廓级摄取校验 FAIL 即停（T40-2）。"""
        bad = json.loads(json.dumps(GOLD_PLAN))
        bad["zones"][0]["outline_mm"] = [{
            "outer": [[0, 0], [10000, 10000], [10000, 0], [0, 10000]],
            "holes": [], "arcs": []}]  # 自相交
        with pytest.raises(ValueError):
            preprocess(bad, str(tmp_path / "derived"))

    def test_preprocess_deterministic(self, tmp_path):
        out1 = tmp_path / "a"
        out2 = tmp_path / "b"
        preprocess(GOLD_PLAN, str(out1))
        preprocess(GOLD_PLAN, str(out2))
        assert (out1 / "floors.json").read_bytes() == (out2 / "floors.json").read_bytes()


class TestBuildZonePack:
    """T41：zone 打包（geom 段 + 代表层切片 + vocab 裁剪 + 金例卡片指针）。"""

    def test_zone_pack_has_geom(self, tmp_path):
        out = tmp_path / "derived"
        preprocess(GOLD_PLAN, str(out))
        pack = json.loads((out / "podium.json").read_text(encoding="utf-8"))
        assert "geom" in pack
        assert pack["geom"]["area_sqm"] > 0

    def test_zone_pack_has_representative_slice(self, tmp_path):
        out = tmp_path / "derived"
        preprocess(GOLD_PLAN, str(out))
        pack = json.loads((out / "podium.json").read_text(encoding="utf-8"))
        assert "floors" in pack
        assert "f1" in pack["floors"]
        assert "outline_mm" in pack["floors"]["f1"]

    def test_zone_pack_vocab_cropped(self, tmp_path):
        """vocab 裁剪：按 zone.function 裁房间词汇。"""
        out = tmp_path / "derived"
        preprocess(GOLD_PLAN, str(out))
        pack = json.loads((out / "podium.json").read_text(encoding="utf-8"))
        assert "vocab" in pack or "rules" in pack or "program" in pack
        # program 来自 plan zone.program（词汇裁剪载体）
        assert "program" in pack["vocab"]

    def test_zone_pack_gold_cards(self, tmp_path):
        """金例卡片指针（top-2）。"""
        out = tmp_path / "derived"
        preprocess(GOLD_PLAN, str(out))
        pack = json.loads((out / "podium.json").read_text(encoding="utf-8"))
        assert "gold_cards" in pack
        assert isinstance(pack["gold_cards"], list)


class TestSkeletonBase:
    """D35：skeleton 底座机械生成——outline/core anchor 从 plan 注入（坐标根基唯一）。

    主 agent 读底座后全权填充修改（axis_grid/typology/core.extent/main_partitions...）；
    底座只锁坐标事实，避免主 agent 重写坐标导致错位。
    """

    def _plan_with_anchor(self, anchor):
        plan = json.loads(json.dumps(GOLD_PLAN))
        if anchor is not None:
            plan["zones"][1]["core_anchor_mm"] = anchor
        return plan

    def test_base_outline_inherited_verbatim(self, tmp_path):
        """outline 机械继承 plan outline_mm（原样搬运，不重写）。"""
        plan = self._plan_with_anchor([30000, 31000])
        out = tmp_path / "derived"
        preprocess(plan, str(out))
        base = json.loads((out / "skeleton_base.json").read_text(encoding="utf-8"))
        tower = next(z for z in base["zones"] if z["zone"] == "tower")
        assert tower["outline"] == plan["zones"][1]["outline_mm"]

    def test_base_outline_multi_block_and_arcs(self):
        """多块 + 真弧 outline 原样继承。"""
        plan = self._plan_with_anchor(None)
        plan["zones"][0]["outline_mm"] = [
            {"outer": {"vertices": [[0, 0], [30000, 0], [30000, 20000], [0, 20000]],
                       "arcs": [{"at": 1, "center": [30000, 0], "radius": 5000,
                                 "a0": 0.0, "a1": 90.0}]},
             "holes": [], "arcs": []},
            {"outer": [[40000, 0], [60000, 0], [60000, 40000], [40000, 40000]],
             "holes": [], "arcs": []},
        ]
        base = build_skeleton_base(plan)
        podium = next(z for z in base["zones"] if z["zone"] == "podium")
        assert len(podium["outline"]) == 2
        assert podium["outline"][0]["outer"]["arcs"][0]["radius"] == 5000

    def test_base_core_anchor_injected_single(self):
        """单核：core_anchor_mm 点 → core.anchor 锁死。"""
        base = build_skeleton_base(self._plan_with_anchor([30000, 31000]))
        tower = next(z for z in base["zones"] if z["zone"] == "tower")
        assert tower["core"]["anchor"] == [30000.0, 31000.0]

    def test_base_core_anchor_injected_multi(self):
        """多核：core_anchor_mm 数组 → core 数组带 id（D31）。"""
        base = build_skeleton_base(self._plan_with_anchor([[20000, 31000], [40000, 31000]]))
        tower = next(z for z in base["zones"] if z["zone"] == "tower")
        assert isinstance(tower["core"], list)
        assert len(tower["core"]) == 2
        assert tower["core"][0]["id"] == "c0"
        assert tower["core"][0]["anchor"] == [20000.0, 31000.0]
        assert tower["core"][1]["anchor"] == [40000.0, 31000.0]

    def test_base_core_none_when_no_anchor(self):
        """无 core_anchor_mm → core None（G-01 core 可选）。"""
        base = build_skeleton_base(self._plan_with_anchor(None))
        podium = next(z for z in base["zones"] if z["zone"] == "podium")
        assert podium["core"] is None

    def test_base_agent_fill_fields_empty(self):
        """主 agent 全权填充字段为空/缺省（axis_grid 不在底座——主 agent 决策）。"""
        base = build_skeleton_base(self._plan_with_anchor([30000, 31000]))
        tower = next(z for z in base["zones"] if z["zone"] == "tower")
        assert "axis_grid" not in tower          # 主 agent 决策（轴网是设计，非继承）
        assert tower["corridor"] is None
        assert tower["main_partitions"] == []
        assert tower["special_openings"] == []

    def test_base_frame_from_site(self):
        """frame 从 plan site 继承（origin/north_deg），units 固定 mm。"""
        base = build_skeleton_base(self._plan_with_anchor(None))
        assert base["frame"]["units"] == "mm"
        assert base["frame"]["origin"] == "lot_southwest"
        assert base["frame"]["north_deg"] == 0

    def test_base_written_to_derived(self, tmp_path):
        """底座落盘 derived/skeleton_base.json。"""
        out = tmp_path / "derived"
        preprocess(self._plan_with_anchor([30000, 31000]), str(out))
        assert (out / "skeleton_base.json").exists()

    def test_base_deterministic(self, tmp_path):
        """底座字节级确定（canon 纪律）。"""
        plan = self._plan_with_anchor([30000, 31000])
        out1, out2 = tmp_path / "a", tmp_path / "b"
        preprocess(plan, str(out1))
        preprocess(plan, str(out2))
        assert (out1 / "skeleton_base.json").read_bytes() == \
               (out2 / "skeleton_base.json").read_bytes()
