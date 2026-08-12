import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = REPO_ROOT / "skills" / "aidxfv" / "v1" / "scripts" / "flows"
SKILL_MD = REPO_ROOT / "skills" / "aidxfv" / "v1" / "SKILL.md"

sys.path.insert(0, str(FLOWS_DIR))

ezdxf = pytest.importorskip("ezdxf")

import cad_script_lib


@pytest.fixture(autouse=True)
def _fresh_state():
    cad_script_lib.reset_state()
    yield
    cad_script_lib.reset_state()


def _new_doc():
    return ezdxf.new()


GOOD_SCRIPT = '''
PARAMS = {"width": 10.0, "radius": 1.5, "name": "W:circle:1"}
import ezdxf
import cad_script_lib

def build(params, out_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    cad_script_lib.add_entity(msp, "LINE", layer="WALL", start=(0, 0), end=(params["width"], 0))
    return cad_script_lib.write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, "out.dxf")
'''


def _write_script(tmp_path, body):
    script = tmp_path / "script.py"
    script.write_text(body, encoding="utf-8")
    return script


class TestContract:
    def test_good_script_passes(self, tmp_path):
        assert cad_script_lib.validate_script_contract(
            _write_script(tmp_path, GOOD_SCRIPT)) == []

    def test_missing_params(self, tmp_path):
        body = GOOD_SCRIPT.replace(
            'PARAMS = {"width": 10.0, "radius": 1.5, "name": "W:circle:1"}\n', "")
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("缺少顶层 PARAMS" in e for e in errors)

    def test_params_not_literal_dict(self, tmp_path):
        body = GOOD_SCRIPT.replace(
            'PARAMS = {"width": 10.0, "radius": 1.5, "name": "W:circle:1"}',
            'PARAMS = dict(width=10.0)')
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("字面量 dict" in e for e in errors)

    def test_params_not_json_compatible(self, tmp_path):
        body = GOOD_SCRIPT.replace(
            'PARAMS = {"width": 10.0, "radius": 1.5, "name": "W:circle:1"}',
            'PARAMS = {"width": {1, 2}}')
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("JSON-compatible" in e for e in errors)

    def test_missing_build(self, tmp_path):
        body = GOOD_SCRIPT.replace("def build(params, out_path):", "def _build(params, out_path):")
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("缺少顶层 build" in e for e in errors)

    def test_build_arity(self, tmp_path):
        body = GOOD_SCRIPT.replace("def build(params, out_path):", "def build(params):")
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("build 入口签名" in e for e in errors)

    def test_missing_main_guard(self, tmp_path):
        body = GOOD_SCRIPT.replace('if __name__ == "__main__":', "if False:")
        errors = cad_script_lib.validate_script_contract(_write_script(tmp_path, body))
        assert any("__main__" in e for e in errors)

    def test_syntax_error(self, tmp_path):
        errors = cad_script_lib.validate_script_contract(
            _write_script(tmp_path, "def broken(:"))
        assert errors and "语法错误" in errors[0]


class TestIdentity:
    def test_auto_key_format_and_increment(self):
        doc = _new_doc()
        msp = doc.modelspace()
        e1 = cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                       start=(0, 0), end=(1, 1))
        e2 = cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                       start=(1, 1), end=(2, 2))
        e3 = cad_script_lib.add_entity(msp, "CIRCLE", layer="WALL",
                                       center=(0, 0), radius=1.0)
        assert cad_script_lib.get_entity_key(e1) == "WALL:line:1"
        assert cad_script_lib.get_entity_key(e2) == "WALL:line:2"
        assert cad_script_lib.get_entity_key(e3) == "WALL:circle:1"

    def test_deterministic_across_runs(self):
        def build_once():
            cad_script_lib.reset_state()
            doc = _new_doc()
            msp = doc.modelspace()
            cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                      start=(0, 0), end=(1, 1))
            cad_script_lib.add_entity(msp, "CIRCLE", layer="COL",
                                      center=(0, 0), radius=0.5)
            cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                      start=(1, 1), end=(2, 2))
            return [cad_script_lib.get_entity_key(e) for e in msp]

        assert build_once() == build_once()

    def test_explicit_key_wins(self):
        doc = _new_doc()
        msp = doc.modelspace()
        e = cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                      key="custom:line:99", start=(0, 0), end=(1, 1))
        assert cad_script_lib.get_entity_key(e) == "custom:line:99"
        e2 = cad_script_lib.add_entity(msp, "LINE", layer="WALL",
                                       start=(0, 0), end=(1, 1))
        assert cad_script_lib.get_entity_key(e2) == "WALL:line:1"

    def test_get_entity_key_none_without_xdata(self):
        doc = _new_doc()
        msp = doc.modelspace()
        e = msp.add_line((0, 0), (1, 1))
        assert cad_script_lib.get_entity_key(e) is None

    def test_appid_registered(self):
        doc = _new_doc()
        msp = doc.modelspace()
        cad_script_lib.add_entity(msp, "LINE", start=(0, 0), end=(1, 1))
        assert "AIDXF" in doc.appids
        assert cad_script_lib.APPID == "AIDXF"

    def test_unknown_kind_raises(self):
        doc = _new_doc()
        with pytest.raises(ValueError, match="未知实体类型"):
            cad_script_lib.add_entity(doc.modelspace(), "SPLINE")


class TestEntities:
    def test_line(self):
        msp = _new_doc().modelspace()
        e = cad_script_lib.add_entity(msp, "LINE", layer="W",
                                      start=(0, 0), end=(3, 4))
        assert e.dxftype() == "LINE"
        assert tuple(e.dxf.start) == (0, 0, 0) or tuple(e.dxf.start)[:2] == (0, 0)
        assert tuple(e.dxf.end)[:2] == (3, 4)
        assert e.dxf.layer == "W"
        assert cad_script_lib.get_entity_key(e) == "W:line:1"

    def test_circle(self):
        msp = _new_doc().modelspace()
        e = cad_script_lib.add_entity(msp, "CIRCLE", center=(1, 2), radius=2.5)
        assert e.dxftype() == "CIRCLE"
        assert e.dxf.radius == 2.5
        assert tuple(e.dxf.center)[:2] == (1, 2)
        assert cad_script_lib.get_entity_key(e) is not None

    def test_arc(self):
        msp = _new_doc().modelspace()
        e = cad_script_lib.add_entity(msp, "ARC", center=(0, 0), radius=1.0,
                                      start_angle=0.0, end_angle=90.0)
        assert e.dxftype() == "ARC"
        assert e.dxf.radius == 1.0
        assert e.dxf.end_angle == 90.0
        assert cad_script_lib.get_entity_key(e) is not None

    def test_lwpolyline_with_bulge(self):
        msp = _new_doc().modelspace()
        pts = [(0, 0, 0, 0, 0.5), (1, 0), (2, 1)]
        e = cad_script_lib.add_entity(msp, "LWPOLYLINE", points=pts,
                                      format="xyseb", closed=True)
        assert e.dxftype() == "LWPOLYLINE"
        assert e.closed is True
        out = list(e.get_points("xyseb"))
        assert out[0][4] == pytest.approx(0.5)
        assert cad_script_lib.get_entity_key(e) is not None

    def test_text(self):
        msp = _new_doc().modelspace()
        e = cad_script_lib.add_entity(msp, "TEXT", text="标注",
                                      insert=(1, 1), height=3.0)
        assert e.dxftype() == "TEXT"
        assert e.dxf.text == "标注"
        assert e.dxf.height == 3.0
        assert tuple(e.dxf.insert)[:2] == (1, 1)
        assert cad_script_lib.get_entity_key(e) is not None

    def test_mtext(self):
        msp = _new_doc().modelspace()
        e = cad_script_lib.add_entity(msp, "MTEXT", text="多行", insert=(2, 2))
        assert e.dxftype() == "MTEXT"
        assert e.text == "多行"
        assert cad_script_lib.get_entity_key(e) is not None

    def test_insert(self):
        doc = _new_doc()
        doc.blocks.new(name="BLK")
        msp = doc.modelspace()
        e = cad_script_lib.add_entity(msp, "INSERT", name="BLK", insert=(5, 5))
        assert e.dxftype() == "INSERT"
        assert e.dxf.name == "BLK"
        assert tuple(e.dxf.insert)[:2] == (5, 5)
        assert cad_script_lib.get_entity_key(e) is not None


ORIGIN_SCRIPT = '''
PARAMS = {"width": 10.0, "name": "W:circle:1"}
import ezdxf
import cad_script_lib

def build(params, out_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    cad_script_lib.add_entity(msp, "CIRCLE", key=params["name"], center=(0, 0), radius=params["width"])
    cad_script_lib.add_entity(msp, "LINE", key="lit:line:1", start=(0, 0), end=(1, 1))
    return cad_script_lib.write_and_validate(doc, out_path)

if __name__ == "__main__":
    build(PARAMS, "out.dxf")
'''


def _run_build(script: Path, out_path: Path):
    src = script.read_text(encoding="utf-8")
    g = {"__name__": "script_under_test"}
    exec(compile(src, str(script), "exec"), g)
    return g["build"](g["PARAMS"], out_path)


class TestWriteAndValidate:
    def test_saveas_and_audit_pass(self, tmp_path):
        script = _write_script(tmp_path, GOOD_SCRIPT)
        out = tmp_path / "out.dxf"
        assert _run_build(script, out) is True
        doc = ezdxf.readfile(out)
        assert len(doc.modelspace()) == 1

    def test_map_sidecar_schema(self, tmp_path):
        script = _write_script(tmp_path, ORIGIN_SCRIPT)
        out = tmp_path / "out.dxf"
        assert _run_build(script, out) is True
        map_path = Path(str(out) + ".map.json")
        data = json.loads(map_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data
        for key, entry in data.items():
            for field in ("line", "col", "snippet", "origin", "params_keys"):
                assert field in entry, f"{key} 缺字段 {field}"

    def test_origin_classification(self, tmp_path):
        script = _write_script(tmp_path, ORIGIN_SCRIPT)
        out = tmp_path / "out.dxf"
        _run_build(script, out)
        data = json.loads(Path(str(out) + ".map.json").read_text(encoding="utf-8"))
        assert data["W:circle:1"]["origin"] == "params"
        assert "name" in data["W:circle:1"]["params_keys"]
        assert data["W:circle:1"]["params_keys"] == ["name", "width"]
        assert data["lit:line:1"]["origin"] == "literal"
        assert data["lit:line:1"]["params_keys"] == []


class TestDocDrift:
    """SKILL.md 引用的 cad_script_lib.<name> 必须在实现中存在(漂移防护)。"""

    def test_skill_md_referenced_names_exist(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        documented = set(re.findall(r"cad_script_lib\.(\w+)", text))
        documented.discard("py")  # 排除路径引用 cad_script_lib.py
        assert documented, "SKILL.md 应引用 cad_script_lib.<name>"
        for name in documented:
            assert hasattr(cad_script_lib, name), \
                f"cad_script_lib 缺少 SKILL.md 引用的 {name}"
