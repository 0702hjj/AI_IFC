"""Interval subtraction: the single source of broken-wall geometry.

Wall faces, poché fill, and dimension chains all consume the same cuts
list so their breaks always align.
"""

from __future__ import annotations

Interval = tuple[float, float]


def subtract_intervals(span: Interval, cuts: list[Interval]) -> list[Interval]:
    """Remove `cuts` from `span`, returning the remaining pieces in order."""

    start, end = span
    pieces: list[Interval] = []
    cursor = start
    for cut_start, cut_end in sorted(cuts):
        if cut_start > cursor:
            pieces.append((cursor, min(cut_start, end)))
        cursor = max(cursor, cut_end)
    if cursor < end:
        pieces.append((cursor, end))
    return pieces
