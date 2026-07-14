"""
grid -- minimal ARC grid helpers for the single-foreground-pixel task class
(data/ARC_easy_a). Pure Python: PySOAR is the SOAR *kernel* (control flow), grid
arithmetic lives here -- the faithful split (Soar itself does grid/number work in
RHS functions / SVS, not in the decision core).
"""

from __future__ import annotations

from typing import Optional

Grid = list[list[int]]


def dims(g: Grid) -> tuple[int, int]:
    return len(g), len(g[0])


def foreground_pixel(g: Grid) -> Optional[tuple[int, int, int]]:
    """The single non-zero pixel as (row, col, color), or None."""
    found = None
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v != 0:
                if found is not None:
                    return None  # not a single-pixel grid
                found = (r, c, v)
    return found


def blank(h: int, w: int) -> Grid:
    return [[0] * w for _ in range(h)]


def with_pixel(h: int, w: int, r: int, c: int, color: int) -> Grid:
    g = blank(h, w)
    if 0 <= r < h and 0 <= c < w:
        g[r][c] = color
    return g
