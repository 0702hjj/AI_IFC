import importlib.util
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "tools" / "skill_pack_aiifc.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "skill_pack_aiifc",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

packer = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = packer
MODULE_SPEC.loader.exec_module(packer)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SKILL = REPO_ROOT / "skills" / "aiifc"

SKILL_MD = """---
name: {name}
description: test skill
---
# Test
"""


def _make_skill(root: Path, name: str = "aiifc") -> Path:
    """Create a minimal valid skill dir under root."""
    skill = root / name
    required = [
        "SKILL.md",
        "requirements.txt",
        "references/SDK_OVERVIEW.md",
        "references/MODELING_WORKFLOWS.md",
        "references/docs/api/README.md",
        "references/docs/flows/README.md",
        "references/docs/flows/script_lib.py",
        "references/docs/flows/skeleton.py",
        "references/docs/flows/design_review.py",
        "references/docs/flows/ifc_inspect.py",
        "references/docs/flows/dxf_from_design.py",
        "templates/build_skeleton.py",
        "workflows/PLAN_DXF_IFC.md",
        "hooks/README.md",
        "hooks/claude-settings.json",
        "hooks/opencode-plugin.ts",
        "hooks/validate_script.py",
        "hooks/validate_script.sh",
    ]
    for rel in required:
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        SKILL_MD.format(name=name), encoding="utf-8"
    )
    return skill


class TestAiifcSkillPackValidate(unittest.TestCase):
    def test_validate_real_skill_passes(self):
        packer.validate(REAL_SKILL, strict_noise=False)

    def test_validate_missing_required_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "requirements.txt").unlink()
            with self.assertRaises(FileNotFoundError):
                packer.validate(skill)

    def test_validate_frontmatter_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="wrongname"), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                packer.validate(skill)

    def test_validate_noise_rejected_when_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "references/docs/flows/__pycache__").mkdir(parents=True)
            (skill / "references/docs/flows/__pycache__/skeleton.pyc").write_bytes(b"\x00")
            with self.assertRaises(ValueError):
                packer.validate(skill, strict_noise=True)

    def test_validate_noise_tolerated_when_not_strict(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "references/docs/flows/__pycache__").mkdir(parents=True)
            (skill / "references/docs/flows/__pycache__/skeleton.pyc").write_bytes(b"\x00")
            packer.validate(skill, strict_noise=False)


class TestAiifcSkillPackBuild(unittest.TestCase):
    def test_build_copies_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            out = root / "out"
            result = packer.build(skill_root=skill, output_root=out, skill_name="aiifc")
            self.assertTrue(result.skill_root.exists())
            self.assertTrue((result.skill_root / "SKILL.md").exists())
            self.assertTrue((result.skill_root / "references/SDK_OVERVIEW.md").exists())
            self.assertIsNone(result.archive_path)

    def test_build_excludes_noise_in_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            (skill / "references/docs/flows/__pycache__").mkdir(parents=True)
            (skill / "references/docs/flows/__pycache__/x.pyc").write_bytes(b"\x00")
            out = root / "out"
            result = packer.build(skill_root=skill, output_root=out, skill_name="aiifc")
            noise = list(result.skill_root.rglob("*.pyc")) + list(
                result.skill_root.rglob("__pycache__")
            )
            self.assertEqual(noise, [])

    def test_build_archive_creates_clean_tar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            out = root / "out"
            result = packer.build(
                skill_root=skill, output_root=out, skill_name="aiifc", archive=True
            )
            self.assertIsNotNone(result.archive_path)
            with tarfile.open(result.archive_path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("aiifc/SKILL.md", names)
            self.assertIn("aiifc/references/docs/flows/design_review.py", names)
            self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in names))

    def test_build_archive_contains_hooks(self):
        """W-0025: hooks（校验即事件）必须打进可分发归档。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            out = root / "out"
            result = packer.build(
                skill_root=skill, output_root=out, skill_name="aiifc", archive=True
            )
            self.assertIsNotNone(result.archive_path)
            with tarfile.open(result.archive_path, "r:gz") as tar:
                names = tar.getnames()
            for rel in ("README.md", "claude-settings.json", "opencode-plugin.ts",
                        "validate_script.py", "validate_script.sh"):
                self.assertIn(f"aiifc/hooks/{rel}", names, f"归档缺少 hooks/{rel}")

    def test_build_copy_keeps_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            out = root / "out"
            result = packer.build(skill_root=skill, output_root=out, skill_name="aiifc")
            self.assertTrue((result.skill_root / "hooks/validate_script.py").is_file())


class TestAiifcSkillPackRealBundle(unittest.TestCase):
    def test_real_skill_builds_and_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = packer.build(
                skill_root=REAL_SKILL,
                output_root=out,
                skill_name="aiifc",
                archive=True,
            )
            self.assertTrue(result.skill_root.exists())
            self.assertIsNotNone(result.archive_path)
            self.assertTrue(result.archive_path.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
