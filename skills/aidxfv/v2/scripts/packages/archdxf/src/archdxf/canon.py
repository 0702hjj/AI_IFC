"""Post-save canonicalization for byte-identical DXF output.

ezdxf registers CLASSES entries in process-dependent order (hash
randomization); CAD readers ignore CLASS order, so sorting the section
makes output independent of process history. Geometry is unaffected.

Implementation: group-tag stream parse. DXF is a flat list of
(code, value) pairs; we walk it once, lift out the CLASSES section's
CLASS entries, sort them, and splice them back.
"""

from __future__ import annotations

from pathlib import Path


def _pairs(lines: list[str]):
    it = iter(range(0, len(lines) - 1, 2))
    for i in it:
        yield i, lines[i].strip(), lines[i + 1]


def canonicalize_dxf(path: str | Path) -> None:
    """Sort the CLASSES section of a saved DXF file, in place."""

    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    classes_range: tuple[int, int] | None = None
    depth_section = False
    for i, code, value_line in _pairs(lines):
        value = value_line.strip()
        if code == "0" and value == "SECTION":
            depth_section = True
        elif code == "2" and depth_section:
            depth_section = False
            if value == "CLASSES":
                start = i + 2
                j = start
                while not (lines[j].strip() == "0" and lines[j + 1].strip() == "ENDSEC"):
                    j += 2
                classes_range = (start, j)
        elif code == "0" and value == "ENDSEC":
            depth_section = False

    if classes_range is None:
        return

    start, end = classes_range
    body = lines[start:end]
    entries = []
    current: list[str] = []
    for k, code, _value in _pairs(body):
        if code == "0" and current:
            entries.append(current)
            current = []
        current.extend([body[k], body[k + 1]])
    if current:
        entries.append(current)

    entries.sort(key=lambda e: "".join(e))
    lines[start:end] = [line for entry in entries for line in entry]
    path.write_text("".join(lines), encoding="utf-8")
