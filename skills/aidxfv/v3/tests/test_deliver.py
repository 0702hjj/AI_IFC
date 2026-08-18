"""deliver.py 测试（T44）：confirmed 封存 + building.json。"""

import json
from pathlib import Path

import pytest

from flowops.deliver import deliver


class TestDeliver:
    def _confirmed_floor(self, tmp_path, name="f1"):
        """构造 confirmed 层产物。"""
        mission_dir = tmp_path / "missions" / f"{name}.rooms"
        mission_dir.mkdir(parents=True, exist_ok=True)
        # floor.dxf 占位
        (mission_dir / "floor.dxf").write_bytes(b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
        # rooms.json
        (mission_dir / "rooms.json").write_text(
            json.dumps({"floor": name, "rooms": [{"id": "a", "area_sqm": 10}]}),
            encoding="utf-8")
        return mission_dir

    def test_deliver_creates_deliver_dir(self, tmp_path):
        self._confirmed_floor(tmp_path, "f1")
        result = deliver("test_project", str(tmp_path))
        assert (tmp_path / "deliver").exists()

    def test_deliver_building_json_schema(self, tmp_path):
        self._confirmed_floor(tmp_path, "f1")
        self._confirmed_floor(tmp_path, "f2")
        deliver("test_project", str(tmp_path))
        building_path = tmp_path / "deliver" / "building.json"
        assert building_path.exists()
        building = json.loads(building_path.read_text(encoding="utf-8"))
        # 过 T04 building schema
        from flowops.validate import validate_building
        assert validate_building(building) == []

    def test_deliver_floors_mapped(self, tmp_path):
        self._confirmed_floor(tmp_path, "f1")
        self._confirmed_floor(tmp_path, "f2")
        deliver("test_project", str(tmp_path))
        building = json.loads((tmp_path / "deliver" / "building.json").read_text())
        floors = {f["floor"] for f in building["floors"]}
        assert floors == {"f1", "f2"}

    def test_deliver_checksums(self, tmp_path):
        self._confirmed_floor(tmp_path, "f1")
        deliver("test_project", str(tmp_path))
        building = json.loads((tmp_path / "deliver" / "building.json").read_text())
        # checksums 与 floors 的 sha256 对应
        for f in building["floors"]:
            assert f["sha256"] in building["checksums"].values()

    def test_deliver_deterministic(self, tmp_path):
        self._confirmed_floor(tmp_path, "f1")
        out1 = tmp_path / "d1"
        out2 = tmp_path / "d2"
        deliver("test_project", str(tmp_path), deliver_dir=str(out1))
        deliver("test_project", str(tmp_path), deliver_dir=str(out2))
        assert (out1 / "building.json").read_bytes() == (out2 / "building.json").read_bytes()
