#!/usr/bin/env python3
"""Build a distributable Agent Skills bundle for the aiifc skill.

Unlike simplecadapi's skill_pack (which GENERATES a skill from SDK source),
the aiifc skill is a hand-maintained directory (SKILL.md + references/).
This packager VALIDATES that directory's integrity, copies it to an output
root, and optionally produces a <name>.tar.gz archive.

The bundle is agent-agnostic: any tool that reads the Anthropic Agent Skills
layout (SKILL.md + references/) can consume it (opencode, Claude Code, etc.).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKILL_NAME = "aiifc"
DEFAULT_SKILL_DIR = Path("skills") / DEFAULT_SKILL_NAME
DEFAULT_OUTPUT_ROOT = Path("skills/dist")

# Subpaths that must exist in a valid aiifc skill bundle.
REQUIRED_PATHS = (
    "SKILL.md",
    "requirements.txt",
    "references/SDK_OVERVIEW.md",
    "references/MODELING_WORKFLOWS.md",
    "references/docs/api/README.md",
    "references/docs/flows/README.md",
    "references/docs/flows/skeleton.py",
    "references/docs/flows/design_review.py",
    "references/docs/flows/ifc_inspect.py",
    "templates/build_skeleton.py",
)

# Anything matching these is considered build noise, not skill content.
FORBIDDEN_SUFFIXES = (".pyc", ".pyo")
FORBIDDEN_DIRS = {"__pycache__", ".git", ".DS_Store", "node_modules", ".venv"}


@dataclass(frozen=True)
class BuildResult:
    """Result object for a completed build."""

    skill_root: Path
    archive_path: Path | None


def _validate_frontmatter(skill_root: Path) -> None:
    """Check SKILL.md frontmatter: name matches dir, description non-empty."""
    skill_file = skill_root / "SKILL.md"
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    in_frontmatter = False
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    name = fields.get("name", "")
    if name != skill_root.name:
        raise ValueError(
            f"SKILL.md frontmatter name {name!r} != skill directory {skill_root.name!r}"
        )
    if not fields.get("description", ""):
        raise ValueError("SKILL.md frontmatter description is empty")


def _scan_for_noise(skill_root: Path) -> list[Path]:
    """Return build-noise paths that should not ship in a skill bundle."""
    noise: list[Path] = []
    for path in skill_root.rglob("*"):
        if path.is_dir():
            if path.name in FORBIDDEN_DIRS:
                noise.append(path)
        elif path.suffix in FORBIDDEN_SUFFIXES:
            noise.append(path)
    return noise


def validate(skill_root: Path, strict_noise: bool = True) -> None:
    """Validate a skill directory before/after packaging.

    - existence + required paths + frontmatter: always checked.
    - strict_noise=True rejects __pycache__/.pyc (used on the copied bundle,
      where noise would mean the copy dropped or leaked content).
    """
    if not skill_root.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {skill_root}")

    for rel in REQUIRED_PATHS:
        path = skill_root / rel
        if not path.exists():
            raise FileNotFoundError(f"Missing required path: {rel}")

    _validate_frontmatter(skill_root)

    if strict_noise:
        noise = _scan_for_noise(skill_root)
        if noise:
            shown = ", ".join(str(p.relative_to(skill_root)) for p in noise[:5])
            raise ValueError(
                f"Skill bundle must not contain build noise (found {len(noise)}): {shown}"
            )


def build(
    skill_root: Path,
    output_root: Path,
    skill_name: str,
    clean: bool = True,
    archive: bool = False,
    quiet: bool = False,
) -> BuildResult:
    """Copy a validated skill dir to output_root and optionally archive it."""
    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    validate(skill_root, strict_noise=False)

    dest = output_root / skill_name
    if dest.exists() and clean:
        log(f"Removing existing skill directory: {dest}")
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_root, dest, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", "*.pyo", ".git", ".DS_Store"
    ))
    log(f"Copied skill bundle to: {dest}")

    # Re-validate the copy with strict noise check: the copied bundle must be
    # clean (any leak here means the ignore pattern is wrong).
    validate(dest, strict_noise=True)

    archive_path = None
    if archive:
        archive_path = output_root / f"{skill_name}.tar.gz"
        log(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dest, arcname=skill_name)
    return BuildResult(skill_root=dest, archive_path=archive_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package the aiifc skill into a distributable Agent Skills bundle"
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=DEFAULT_SKILL_DIR,
        help=f"Source skill directory (default: {DEFAULT_SKILL_DIR})",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=f"Output directory for the bundle (default: {DEFAULT_OUTPUT_ROOT})",
    )
    parser.add_argument(
        "--skill-name",
        default=DEFAULT_SKILL_NAME,
        help=f"Skill directory name and SKILL.md frontmatter name (default: {DEFAULT_SKILL_NAME})",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove an existing output skill directory before copying",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Create <skill-name>.tar.gz after copying",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output_root = (
        args.output_root.resolve()
        if args.output_root is not None
        else DEFAULT_OUTPUT_ROOT.resolve()
    )
    skill_root = args.skill_dir.resolve()

    try:
        result = build(
            skill_root=skill_root,
            output_root=output_root,
            skill_name=args.skill_name,
            clean=not args.no_clean,
            archive=args.archive,
            quiet=args.quiet,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not args.quiet:
        print("Skill bundle generated successfully.")
        print(f"Skill directory: {result.skill_root}")
        if result.archive_path is not None:
            print(f"Archive path: {result.archive_path}")


if __name__ == "__main__":
    main()
