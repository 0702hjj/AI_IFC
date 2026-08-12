#!/usr/bin/env python3
"""Build a distributable Agent Skills bundle for any skill directory.

Unlike simplecadapi's skill_pack (which GENERATES a skill from SDK source),
skills here are hand-maintained directories (SKILL.md + references/ + ...).
This packager VALIDATES that directory's integrity, copies it to an output
root, and optionally produces a <name>.tar.gz archive.

The bundle is agent-agnostic: any tool that reads the Anthropic Agent Skills
layout (SKILL.md + references/) can consume it (opencode, Claude Code, etc.).

Every skill must provide SKILL.md + requirements.txt (base contract). Skills
known to the SKILL_REGISTRY additionally get a per-skill list of required
subpaths (extended contract) plus a frontmatter name-match check. Unknown
skill names are only held to the base contract (with a warning), so the
packager works for any future skill without code changes.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tarfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SKILL_NAME = "aiifc"
DEFAULT_OUTPUT_ROOT = Path("skills/dist")

# Base contract every skill bundle must satisfy, regardless of registry entry.
BASE_REQUIRED = (
    "SKILL.md",
    "requirements.txt",
)

# Per-skill extended contracts: subpaths that must exist on top of the base.
# Add a new entry here when a skill needs extra integrity guarantees (e.g.
# its MIT LICENSE, vendored runtime, or reference docs).
SKILL_REGISTRY: dict[str, tuple[str, ...]] = {
    "aiifc": (
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
    ),
    "aidxfv1": (
        "LICENSE",
        "agents/",
        "references/",
        "scripts/",
        "steps/",
        "tests/",
    ),
    "aidxfv2": (
        "LICENSE",
        "agents/",
        "references/",
        "scripts/",
        "steps/",
        "tests/",
    ),
    "aibim-orchestrator": (
        "references/SUBAGENTS.md",
        "references/RELAY_CONTRACT.md",
        "references/fixtures/plan.sample.json",
        "examples/opencode/agent/aibim-orchestrator.md",
        "examples/opencode/agent/ifc-agent.md",
        "examples/opencode/agent/cad-agent.md",
        "CHANGELOG.md",
    ),
}

# Anything matching these is considered build noise, not skill content.
FORBIDDEN_SUFFIXES = (".pyc", ".pyo")
FORBIDDEN_DIRS = {"__pycache__", ".git", ".DS_Store", "node_modules", ".venv"}


@dataclass(frozen=True)
class BuildResult:
    """Result object for a completed build."""

    skill_root: Path
    archive_path: Path | None


def _parse_frontmatter(skill_root: Path) -> dict[str, str]:
    """Parse SKILL.md YAML frontmatter into a flat {key: value} dict."""
    skill_file = skill_root / "SKILL.md"
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


def skill_version(skill_root: Path) -> str:
    """Return the SKILL.md frontmatter version, or "" when absent."""
    return _parse_frontmatter(skill_root).get("version", "")


def _validate_frontmatter(skill_root: Path, skill_name: str | None = None) -> None:
    """Check SKILL.md frontmatter: parses, name/description non-empty.

    When skill_name is given (a registered/known skill), the frontmatter
    name must match it — catches SKILL.md content belonging to another skill.
    """
    fields = _parse_frontmatter(skill_root)
    name = fields.get("name", "")
    if not name:
        raise ValueError("SKILL.md frontmatter name is empty")
    if not fields.get("description", ""):
        raise ValueError("SKILL.md frontmatter description is empty")
    if skill_name is not None and name != skill_name:
        raise ValueError(
            f"SKILL.md frontmatter name {name!r} != skill name {skill_name!r}"
        )
    if skill_name is not None and not fields.get("version", ""):
        raise ValueError(
            f"SKILL.md frontmatter version is empty (skill {skill_name!r})"
        )


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


def validate(
    skill_root: Path,
    strict_noise: bool = True,
    skill_name: str | None = None,
    warn_unknown: bool = True,
) -> None:
    """Validate a skill directory before/after packaging.

    - base required paths (SKILL.md + requirements.txt) + frontmatter: always.
    - if the skill name is registered: its extended paths + frontmatter
      name-match are also enforced.
    - unknown skill names: base contract only, with a warning.
    - strict_noise=True rejects __pycache__/.pyc (used on the copied bundle,
      where noise would mean the copy dropped or leaked content).
    """
    if not skill_root.is_dir():
        raise FileNotFoundError(f"Skill directory not found: {skill_root}")

    skill_name = skill_name or skill_root.name
    extended = SKILL_REGISTRY.get(skill_name)

    for rel in BASE_REQUIRED:
        path = skill_root / rel
        if not path.exists():
            raise FileNotFoundError(f"Missing required path: {rel}")

    if extended is None:
        if warn_unknown:
            print(
                f"Warning: skill {skill_name!r} has no extended contract in "
                "SKILL_REGISTRY; validating base contract only.",
                file=sys.stderr,
            )
    else:
        for rel in extended:
            path = skill_root / rel
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing required path for skill {skill_name!r}: {rel}"
                )

    _validate_frontmatter(skill_root, skill_name=skill_name if extended is not None else None)

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

    validate(skill_root, strict_noise=False, skill_name=skill_name)

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
    # clean (any leak here means the ignore pattern is wrong). The unknown-skill
    # warning was already emitted for the source, so suppress it here.
    validate(dest, strict_noise=True, skill_name=skill_name, warn_unknown=False)

    archive_path = None
    if archive:
        version = skill_version(skill_root)
        if not version:
            raise ValueError(
                "SKILL.md frontmatter version is empty; "
                "cannot produce a versioned archive name"
            )
        archive_path = output_root / f"{skill_name}-{version}.tar.gz"
        log(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dest, arcname=skill_name)
    return BuildResult(skill_root=dest, archive_path=archive_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package any skill directory into a distributable "
        "Agent Skills bundle (validates frontmatter + required paths + noise)"
    )
    parser.add_argument(
        "--skill",
        default=None,
        help=f"Skill name (default: {DEFAULT_SKILL_NAME}); source dir is skills/<name>",
    )
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=None,
        help="Source skill directory; overrides --skill's default dir. "
        "Skill name is inferred from the directory name",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=f"Output directory for the bundle (default: {DEFAULT_OUTPUT_ROOT})",
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
    if args.skill_dir is not None:
        skill_root = args.skill_dir.resolve()
        skill_name = args.skill or skill_root.name
    else:
        skill_name = args.skill or DEFAULT_SKILL_NAME
        skill_root = (Path("skills") / skill_name).resolve()

    try:
        result = build(
            skill_root=skill_root,
            output_root=output_root,
            skill_name=skill_name,
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
