import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"
SCHEMA_MD = REPO_ROOT / "skills" / "aiifc" / "references" / "DESIGN_JSON_SCHEMA.md"

sys.path.insert(0, str(FLOWS_DIR))

import design_builder


def test_schema_doc_example_normalizes_without_field_loss():
    blocks = re.findall(r"```json\n(.*?)```", SCHEMA_MD.read_text(encoding="utf-8"), re.S)
    examples = []
    for b in blocks:
        try:
            d = json.loads(b)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "frame" in d and "floors" in d:
            examples.append(d)
    assert examples, "schema 文档中应存在可解析的完整示例 JSON"

    for design in examples:
        features = design_builder.normalize(design)
        assert features["walls"], "walls 不应丢失"
        src_openings = [
            op for fd in design["floors"].values() for op in fd.get("openings", [])
        ]
        assert len(features["openings"]) == len(src_openings), "openings 不应丢失"
        for got, src in zip(features["openings"], src_openings):
            assert got["along"] == pytest.approx(src["along"])
            assert got["w"] == pytest.approx(src["w"])
            assert got["h"] == pytest.approx(src["h"])
            assert got["sill"] == pytest.approx(src["sill"])
            assert got["type"] == src["type"]

        src_stairs = [
            st for fd in design["floors"].values() for st in fd.get("stairs", [])
        ]
        assert len(features["stairs"]) == len(src_stairs), "stairs 不应丢失"
        for got, src in zip(features["stairs"], src_stairs):
            assert not ("at" in src and "shaft" in src), \
                "楼梯定位 shaft 与 at+size 应二选一"
            assert got["type"] == src["type"]
            assert got["width"] == src.get("width")
            if "shaft" in src:
                assert set(src["shaft"]) <= {"x", "y"}, \
                    "shaft 只能用 schema 定义的 {x, y} 轴网索引键"
                xi, xj = src["shaft"]["x"]
                yk, yl = src["shaft"]["y"]
                ag = design["frame"]["axis_grid"]
                assert got["shaft"] == {
                    "x0": ag["x"][xi], "x1": ag["x"][xj],
                    "y0": ag["y"][yk], "y1": ag["y"][yl],
                }
            else:
                assert got["at"] == [pytest.approx(v) for v in src["at"]]
                assert got["size"] == [pytest.approx(v) for v in src["size"]]

        for sname, fd in design["floors"].items():
            if "roof" in fd:
                assert features["roof"] == fd["roof"], "roof 不应丢失"
