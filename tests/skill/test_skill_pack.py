import importlib.util
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "tools" / "skill_pack.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location(
    "skill_pack",
    MODULE_PATH,
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:
    raise RuntimeError(f"Unable to load module spec for {MODULE_PATH}")

packer = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = packer
MODULE_SPEC.loader.exec_module(packer)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SKILL = REPO_ROOT / "skills" / "aiifc"
REAL_CAD_SKILL = REPO_ROOT / "skills" / "aidxfv" / "v3"
REAL_ORCH_SKILL = REPO_ROOT / "skills" / "aibim-orchestrator"
REAL_PLAN_SKILL = REPO_ROOT / "skills" / "aiplan"

SKILL_MD = """---
name: {name}
description: test skill
version: 0.1.0
---
# Test
"""


def _make_skill(root: Path, name: str = "aiifc") -> Path:
    """Create a minimal valid skill dir under root.

    Required files follow the packer's own contracts: base for every skill,
    plus the extended registry contract when the name is registered.
    """
    skill = root / name
    required = list(packer.BASE_REQUIRED) + list(
        packer.SKILL_REGISTRY.get(name, ())
    )
    for rel in required:
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    (skill / "SKILL.md").write_text(
        SKILL_MD.format(name=name), encoding="utf-8"
    )
    return skill


class TestSkillPackValidate(unittest.TestCase):
    def test_validate_real_skill_passes(self):
        packer.validate(REAL_SKILL, strict_noise=False)

    def test_validate_real_cad_skill_passes(self):
        packer.validate(REAL_CAD_SKILL, strict_noise=False, skill_name="aidxfv3")

    def test_validate_real_orchestrator_skill_passes(self):
        packer.validate(REAL_ORCH_SKILL, strict_noise=False)

    def test_validate_missing_required_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "requirements.txt").unlink()
            with self.assertRaises(FileNotFoundError):
                packer.validate(skill)

    def test_validate_missing_requirements_in_unknown_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "unregistered")
            (skill / "requirements.txt").unlink()
            with self.assertRaises(FileNotFoundError):
                packer.validate(skill)

    def test_validate_unknown_skill_only_base_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "unregistered")
            packer.validate(skill, strict_noise=False)

    def test_validate_frontmatter_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="wrongname"), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                packer.validate(skill)

    def test_validate_unknown_skill_frontmatter_name_not_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "unregistered")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="whatever"), encoding="utf-8"
            )
            packer.validate(skill, strict_noise=False)

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
            (skill / "references/docs/flows/__pycache__/x.pyc").write_bytes(b"\x00")
            packer.validate(skill, strict_noise=False)

    def test_validate_registered_skill_missing_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "aiifc")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="aiifc").replace("version: 0.1.0\n", ""),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                packer.validate(skill)

    def test_validate_unknown_skill_version_not_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = _make_skill(Path(tmp), "unregistered")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="whatever").replace("version: 0.1.0\n", ""),
                encoding="utf-8",
            )
            packer.validate(skill, strict_noise=False)

    def test_real_skills_have_version(self):
        for root, name in (
            (REAL_SKILL, "aiifc"),
            (REAL_CAD_SKILL, "aidxfv3"),
        ):
            self.assertTrue(
                packer.skill_version(root),
                f"{name} SKILL.md frontmatter 缺 version",
            )


class TestSkillPackBuild(unittest.TestCase):
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

    def test_build_archive_requires_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "unregistered")
            (skill / "SKILL.md").write_text(
                SKILL_MD.format(name="unregistered").replace("version: 0.1.0\n", ""),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                packer.build(
                    skill_root=skill, output_root=root / "out",
                    skill_name="unregistered", archive=True,
                )

    def test_build_archive_name_includes_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = _make_skill(root, "aiifc")
            out = root / "out"
            result = packer.build(
                skill_root=skill, output_root=out, skill_name="aiifc", archive=True
            )
            self.assertEqual(result.archive_path, out / "aiifc-0.1.0.tar.gz")


class TestSkillPackRealBundle(unittest.TestCase):
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

    def test_real_cad_skill_builds_and_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = packer.build(
                skill_root=REAL_CAD_SKILL,
                output_root=out,
                skill_name="aidxfv3",
                archive=True,
            )
            self.assertTrue(result.skill_root.exists())
            self.assertIsNotNone(result.archive_path)
            self.assertTrue(result.archive_path.stat().st_size > 0)
            with tarfile.open(result.archive_path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("aidxfv3/SKILL.md", names)
            self.assertTrue(
                any(n.endswith("/LICENSE") for n in names),
                "MIT LICENSE 必须保留在 CAD skill 打包产物中",
            )

    def test_real_orchestrator_skill_builds_and_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = packer.build(
                skill_root=REAL_ORCH_SKILL,
                output_root=out,
                skill_name="aibim-orchestrator",
                archive=True,
            )
            self.assertIsNotNone(result.archive_path)
            with tarfile.open(result.archive_path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("aibim-orchestrator/SKILL.md", names)
            self.assertIn("aibim-orchestrator/references/RELAY_CONTRACT.md", names)
            self.assertIn("aibim-orchestrator/references/SUBAGENTS.md", names)

    def test_real_plan_skill_builds_and_archives(self):
        """aiplan skill 可归档（frontmatter version 是 archive 的硬前提）。"""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dist"
            result = packer.build(
                skill_root=REAL_PLAN_SKILL,
                output_root=out,
                skill_name="aiplan",
                archive=True,
            )
            self.assertTrue(result.skill_root.exists())
            self.assertIsNotNone(result.archive_path)
            self.assertTrue(result.archive_path.stat().st_size > 0)
            with tarfile.open(result.archive_path, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("aiplan/SKILL.md", names)

    def test_real_cad_skill_cli_archive_contains_license(self):
        """`--skill aidxfv3 --skill-dir skills/aidxfv/v3 --archive` 显式名覆盖推断名 v3。"""
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "skill_pack.py",
                "--skill", "aidxfv3",
                "--skill-dir", str(REAL_CAD_SKILL),
                "--output-root", str(Path(tmp) / "dist"),
                "--archive",
                "--quiet",
            ]
            with patch("sys.argv", argv):
                packer.main()
            version = packer.skill_version(REAL_CAD_SKILL)
            archive = Path(tmp) / "dist" / f"aidxfv3-{version}.tar.gz"
            self.assertTrue(archive.exists())
            with tarfile.open(archive, "r:gz") as tar:
                names = tar.getnames()
            self.assertIn("aidxfv3/SKILL.md", names)
            self.assertTrue(
                any(n.endswith("/LICENSE") for n in names),
                "MIT LICENSE 必须保留在 CLI 打包产物中",
            )


if __name__ == "__main__":
    unittest.main()
