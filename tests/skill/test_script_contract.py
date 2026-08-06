import json
import re
import sys
from pathlib import Path

import ifcopenshell
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLOWS_DIR = REPO_ROOT / "skills" / "aiifc" / "references" / "docs" / "flows"
SKILL_MD = REPO_ROOT / "skills" / "aiifc" / "SKILL.md"
FIXTURES = REPO_ROOT / "tests" / "skill" / "fixtures"

sys.path.insert(0, str(FLOWS_DIR))

import build_script_template
import design_builder
import script_lib


class TestDeterministicGuid:
    def test_same_key_twice_identical(self):
        assert script_lib.deterministic_guid("1F:wall:0") == \
            script_lib.deterministic_guid("1F:wall:0")

    def test_different_keys_differ(self):
        assert script_lib.deterministic_guid("1F:wall:0") != \
            script_lib.deterministic_guid("1F:wall:1")

    def test_ifc_base64_format(self):
        guid = script_lib.deterministic_guid("1F:wall:0")
        assert len(guid) == 22
        assert guid[0] in "0123"

    def test_namespace_stable(self):
        import uuid
        assert script_lib.NAMESPACE_AI_IFC == \
            uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class TestAttachDesignKey:
    def test_writes_pset_design_key(self):
        model = ifcopenshell.api.run("project.create_file")
        ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
        wall = script_lib.create_entity(model, "IfcWall", "1F:wall:0")
        script_lib.attach_design_key(model, wall, "1F:wall:0")
        from ifcopenshell.util.element import get_psets
        psets = get_psets(wall)
        assert psets["Pset_AIIFC"]["designKey"] == "1F:wall:0"
        assert wall.GlobalId == script_lib.deterministic_guid("1F:wall:0")

    def test_empty_key_noop(self):
        model = ifcopenshell.api.run("project.create_file")
        ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject")
        wall = script_lib.create_entity(model, "IfcWall", "1F:wall:0")
        script_lib.attach_design_key(model, wall, "")
        from ifcopenshell.util.element import get_psets
        assert "Pset_AIIFC" not in get_psets(wall)


GOOD_SCRIPT = '''PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}

def build(params, out_path):
    pass

if __name__ == "__main__":
    build(PARAMS, "model.ifc")
'''


class TestValidateScriptContract:
    def _write(self, tmp_path, src):
        p = tmp_path / "script.py"
        p.write_text(src, encoding="utf-8")
        return p

    def test_good_script_passes(self, tmp_path):
        assert script_lib.validate_script_contract(self._write(tmp_path, GOOD_SCRIPT)) == []

    def test_missing_params(self, tmp_path):
        src = 'def build(params, out_path):\n    pass\n\nif __name__ == "__main__":\n    pass\n'
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("PARAMS" in e for e in errors)

    def test_params_not_literal(self, tmp_path):
        src = GOOD_SCRIPT.replace('PARAMS = {"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                  'PARAMS = dict(length=5.0)')
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("字面量" in e for e in errors)

    def test_params_not_json_compatible(self, tmp_path):
        src = GOOD_SCRIPT.replace('{"length": 5.0, "height": 3.0, "nested": {"t": 0.2}, "tags": ["a"]}',
                                  '{("tuple",): 1}')
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("JSON-compatible" in e for e in errors)

    def test_missing_build(self, tmp_path):
        src = 'PARAMS = {"a": 1}\n\nif __name__ == "__main__":\n    pass\n'
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("build" in e for e in errors)

    def test_build_bad_signature(self, tmp_path):
        src = 'PARAMS = {"a": 1}\n\ndef build(params):\n    pass\n\nif __name__ == "__main__":\n    pass\n'
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("build(params, out_path)" in e for e in errors)

    def test_missing_main_guard(self, tmp_path):
        src = 'PARAMS = {"a": 1}\n\ndef build(params, out_path):\n    pass\n'
        errors = script_lib.validate_script_contract(self._write(tmp_path, src))
        assert any("__main__" in e for e in errors)

    def test_syntax_error(self, tmp_path):
        errors = script_lib.validate_script_contract(self._write(tmp_path, "def (:\n"))
        assert any("语法错误" in e for e in errors)


class TestTemplateThinWrapper:
    def test_aliases_point_to_script_lib(self):
        assert build_script_template.global_id is script_lib.deterministic_guid
        assert build_script_template.attach_design_identity is script_lib.attach_design_key
        assert build_script_template.create_entity is script_lib.create_entity
        assert build_script_template.NAMESPACE_AI_IFC is script_lib.NAMESPACE_AI_IFC

    def test_build_smoke_and_determinism(self, tmp_path):
        design = json.loads(
            (FIXTURES / "sample_design.json").read_text(encoding="utf-8"))
        features = design_builder.normalize(design)
        fp = tmp_path / "features.json"
        fp.write_text(json.dumps(features), encoding="utf-8")

        out1, out2 = tmp_path / "m1.ifc", tmp_path / "m2.ifc"
        assert build_script_template.build(str(fp), str(out1)) is True
        assert build_script_template.build(str(fp), str(out2)) is True

        m1, m2 = ifcopenshell.open(str(out1)), ifcopenshell.open(str(out2))
        walls1 = sorted(w.GlobalId for w in m1.by_type("IfcWall"))
        walls2 = sorted(w.GlobalId for w in m2.by_type("IfcWall"))
        assert walls1 and walls1 == walls2
        assert m1.by_type("IfcSlab")
        assert m1.by_type("IfcOpeningElement")


class TestSkillDocContractDrift:
    """SKILL.md 的脚本契约 MUST 与 script_lib 实现保持同步(漂移防护)。"""

    def test_skill_md_documents_contract(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        for marker in ("PARAMS", "deterministic_guid", "attach_design_key",
                       "build(params, out_path)", "write_and_validate",
                       "validate_script_contract", "25.", "26.", "27.", "28.", "29."):
            assert marker in text, f"SKILL.md 缺少契约标记: {marker}"

    def test_script_lib_exports_documented_names(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        documented = set(re.findall(r"script_lib\.(\w+)", text))
        assert documented, "SKILL.md 应引用 script_lib.<name>"
        for name in documented:
            assert hasattr(script_lib, name), f"script_lib 缺少 SKILL.md 引用的 {name}"
