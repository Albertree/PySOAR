"""
transformation DSL — 그리드 변형 *동결 원자 하나(coloring)* (씨앗).

손으로 늘리지 않는다 (frozen); 고급 DSL 은 이 원자의 *조합* 으로만 생긴다
(SLICE_1_DEV §5; [[arbor-dsl-taxonomy]]). 이 명세가 semantic DSL
라이브러리의 시작 상태 — Slice 2 의 anti-unification 이 여기서 자란다.
"""

from arbor.procedural_memory.dsl.registry import dsl
from arbor.procedural_memory.dsl.effect import effect


@dsl("transformation", ["grid", "coordinate", "color"], "grid", effect=effect("recolor", "grid"))
def coloring(grid, position, color):
    """grid 의 position=(row, col) 한 셀을 color 로 칠한 *새* 격자 반환."""
    r, c = position
    out = [row[:] for row in grid]
    out[r][c] = color
    return out


@dsl("transformation", ["grid", "size"], "grid", effect=effect("create", "grid"))
def set_grid_size(grid, size):
    """G1 의 차원 선언. **선언형(make_grid 없이)** — 산출은 contents 가 지배하고 size 는 표시·검증용
    주장(Round-3 Grid 객체모델: valid iff size==dims(contents)). set_grid_color 와 동형."""
    return grid                          # size 는 표시·검증용; 산출은 contents 지배


@dsl("transformation", ["grid", "color"], "grid", effect=effect("recolor", "grid"))
def set_grid_color(grid, color):
    """G1 의 base/palette 설정. color 집합의 base(fill) 로 배경 확정 — 나머지 색은 contents 가 채움."""
    return grid                          # base/palette 는 표시·검증용; 산출은 contents 지배(Phase 1)


@dsl("transformation", ["grid", "class"], "grid", effect=effect("create", "grid"))
def set_grid_contents(grid, contents):
    """G1 의 셀 값 = coloring 조합(또는 상수/항등). Phase 1: const grid 그대로, keep=입력."""
    return [list(r) for r in contents] if contents is not None else grid
