"""
transformation DSL — 그리드 변형 *동결 원자 2개* (씨앗).

손으로 늘리지 않는다 (frozen); 고급 DSL 은 이 둘의 *조합* 으로만 생긴다
(SLICE_1_DEV §5; [[arbor-dsl-taxonomy]]). 이 둘의 명세가 semantic DSL
라이브러리의 시작 상태 — Slice 2 의 anti-unification 이 여기서 자란다.
"""

from procedural_memory.dsl.registry import dsl
from procedural_memory.dsl.effect import effect


@dsl("transformation", ["size", "color"], "grid", effect=effect("create", "grid"))
def make_grid(size, fill=0):
    """size={height,width} 격자를 fill 색으로 채워 생성."""
    return [[fill for _ in range(size["width"])] for _ in range(size["height"])]


@dsl("transformation", ["grid", "position", "color"], "grid", effect=effect("recolor", "grid"))
def coloring(grid, position, color):
    """grid 의 position=(row, col) 한 셀을 color 로 칠한 *새* 격자 반환."""
    r, c = position
    out = [row[:] for row in grid]
    out[r][c] = color
    return out

from procedural_memory.dsl.transformation import hodel_transforms  # noqa: F401,E402  (@dsl 발화)
