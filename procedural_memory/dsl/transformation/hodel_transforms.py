# -*- coding: utf-8 -*-
"""arc-dsl(michaelhodel) GRID transform 어휘 vendoring — list[list] 표현.
frozen 원자(make_grid/coloring)와 분리된 확장 어휘. propose 는 effect 일치로 걸린다."""
from collections import Counter
from procedural_memory.dsl.registry import dsl
from procedural_memory.dsl.effect import effect
# toindices 는 selection.hodel_selection 이 canonical 소스 — 재구현하지 않고 재사용.
# import 순서(dsl/__init__.py: util→property→transformation→selection→relation)상
# transformation 이 selection 보다 먼저 로드되지만, selection 은 transformation 에
# 의존하지 않으므로(양방향 아님) 여기서 먼저 당겨써도 순환 import 가 생기지 않는다.
from procedural_memory.dsl.selection.hodel_selection import toindices


def _T(g): return [list(row) for row in zip(*g)]           # transpose


@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot90(grid):
    return [list(r) for r in zip(*grid[::-1])]

@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot180(grid):
    return [list(r[::-1]) for r in grid[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("rotate", "grid"))
def rot270(grid):
    return [list(r) for r in list(zip(*grid))[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def hmirror(grid):
    return [list(r) for r in grid[::-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def vmirror(grid):
    return [list(r[::-1]) for r in grid]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def dmirror(grid):
    return [list(r) for r in zip(*grid)]

@dsl("transformation", ["grid"], "grid", effect=effect("reflect", "grid"))
def cmirror(grid):
    return [list(r) for r in zip(*[row[::-1] for row in grid[::-1]])]

@dsl("transformation", ["grid"], "grid", effect=effect("downscale", "grid"))
def compress(grid):
    ri = {i for i, r in enumerate(grid) if len(set(r)) == 1}
    ci = {j for j in range(len(grid[0])) if len({grid[i][j] for i in range(len(grid))}) == 1}
    return [[v for j, v in enumerate(r) if j not in ci]
            for i, r in enumerate(grid) if i not in ri] or [[]]

@dsl("transformation", ["grid"], "grid", effect=effect("downscale", "grid"))
def trim(grid):
    return [list(r[1:-1]) for r in grid[1:-1]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def tophalf(grid):
    return [list(r) for r in grid[:len(grid) // 2]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def bottomhalf(grid):
    return [list(r) for r in grid[len(grid) // 2 + len(grid) % 2:]]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def lefthalf(grid):
    return [list(r[:len(grid[0]) // 2]) for r in grid]

@dsl("transformation", ["grid"], "grid", effect=effect("crop", "grid"))
def righthalf(grid):
    return [list(r[len(grid[0]) // 2 + len(grid[0]) % 2:]) for r in grid]

@dsl("transformation", ["grid", "color", "color"], "grid", effect=effect("recolor", "grid"))
def replace(grid, replacee, replacer):
    return [[replacer if v == replacee else v for v in r] for r in grid]

@dsl("transformation", ["grid", "color", "color"], "grid", effect=effect("recolor", "grid"))
def switch(grid, a, b):
    return [[a if v == b else (b if v == a else v) for v in r] for r in grid]

def _bg(grid):
    return Counter(v for r in grid for v in r).most_common(1)[0][0]

def _paint(grid, obj_cells):
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for v, (i, j) in obj_cells:
        if 0 <= i < H and 0 <= j < W:
            out[i][j] = v
    return out

@dsl("transformation", ["grid", "object", "position"], "grid", effect=effect("translate", "grid"))
def shift(grid, obj_cells, offset):
    di, dj = offset
    return _paint(grid, frozenset((v, (i + di, j + dj)) for v, (i, j) in obj_cells))

@dsl("transformation", ["grid", "object", "position"], "grid", effect=effect("translate", "grid"))
def move(grid, obj_cells, offset):
    bg = _bg(grid)
    covered = _paint(grid, frozenset((bg, (i, j)) for _, (i, j) in obj_cells))
    di, dj = offset
    return _paint(covered, frozenset((v, (i + di, j + dj)) for v, (i, j) in obj_cells))


# ── Task 8: 나머지 arc-dsl 어휘 (verb 버킷은 브리프 Global Constraints 표) ──────

@dsl("transformation", ["grid", "color", "object"], "grid", effect=effect("fill", "grid"))
def fill(grid, value, patch):
    """patch(색 포함 object 또는 순수 indices) 좌표를 value 로 채운다."""
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for (i, j) in toindices(patch):
        if 0 <= i < H and 0 <= j < W:
            out[i][j] = value
    return out


@dsl("transformation", ["grid", "object"], "grid", effect=effect("fill", "grid"))
def paint(grid, obj):
    """object(색 포함) 를 grid 에 칠한다. — 기존 _paint 헬퍼 재사용."""
    return _paint(grid, obj)


@dsl("transformation", ["grid", "color", "object"], "grid", effect=effect("fill", "grid"))
def underfill(grid, value, patch):
    """patch 좌표 중 배경색인 셀만 value 로 채운다."""
    bg = _bg(grid)
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for (i, j) in toindices(patch):
        if 0 <= i < H and 0 <= j < W and out[i][j] == bg:
            out[i][j] = value
    return out


@dsl("transformation", ["grid", "object"], "grid", effect=effect("fill", "grid"))
def underpaint(grid, obj):
    """obj 를 grid 에 칠하되 배경색인 셀에만."""
    bg = _bg(grid)
    H, W = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for v, (i, j) in obj:
        if 0 <= i < H and 0 <= j < W and out[i][j] == bg:
            out[i][j] = v
    return out


@dsl("transformation", ["grid", "object"], "grid", effect=effect("fill", "grid"))
def cover(grid, patch):
    """patch 를 배경색으로 지운다(= fill 로 배경색 채우기)."""
    return fill(grid, _bg(grid), patch)


# 판단: 원본 arc-dsl recolor(value, patch) -> Object(색 재태깅된 patch, Grid 아님).
# 브리프 Global Constraints 표는 그래도 recolor 를 effect("recolor","grid") 버킷에
# 명시적으로 지정 — 표를 그대로 따르되(§ 지시), out 타입은 실제 반환값(object)으로 정확히
# 적는다. (기존 replace/switch 는 "grid 전체 재색칠"이라 실제로 grid 를 반환 — recolor 는
# "patch 하나의 색만 바꿔 새 object 로" 라 결이 달라 이름이 겹치지 않게 둘 다 유지.)
@dsl("transformation", ["color", "object"], "object", effect=effect("recolor", "grid"))
def recolor(value, patch):
    """patch 의 모든 좌표를 value 색으로 재태깅한 새 object."""
    return frozenset((value, idx) for idx in toindices(patch))


@dsl("transformation", ["grid", "position", "size"], "grid", effect=effect("crop", "grid"))
def crop(grid, start, dims):
    """grid 에서 start=(r,c) 부터 dims=(h,w) 크기만큼 잘라낸 subgrid."""
    si, sj = start
    h, w = dims
    return [row[sj:sj + w] for row in grid[si:si + h]]


@dsl("transformation", ["object", "grid"], "grid", effect=effect("crop", "grid"))
def subgrid(patch, grid):
    """patch 를 담는 최소 bbox subgrid(= crop(grid, ulcorner(patch), shape(patch)))."""
    idx = toindices(patch)
    rows = [i for i, j in idx]
    cols = [j for i, j in idx]
    si, sj = min(rows), min(cols)
    h, w = max(rows) - si + 1, max(cols) - sj + 1
    return crop(grid, (si, sj), (h, w))


@dsl("transformation", ["grid", "grid"], "grid", effect=effect("concat", "grid"))
def hconcat(a, b):
    """두 grid 를 수평(행별 이어붙이기)으로 합친다."""
    return [ra + rb for ra, rb in zip(a, b)]


@dsl("transformation", ["grid", "grid"], "grid", effect=effect("concat", "grid"))
def vconcat(a, b):
    """두 grid 를 수직(행 이어붙이기)으로 합친다."""
    return [row[:] for row in a] + [row[:] for row in b]


# 판단: hsplit/vsplit 은 Grid 하나가 아니라 "grid 목록"을 반환(브리프가 명시한 대로
# selection-like 로 취급) — effect=None, out="list[grid]".
@dsl("transformation", ["grid", "size"], "list[grid]")
def hsplit(grid, n):
    """grid 를 세로줄 n 등분(나머지는 앞쪽 조각이 흡수)."""
    h, w = len(grid), len(grid[0]) // n
    offset = len(grid[0]) % n != 0
    return [crop(grid, (0, w * i + i * offset), (h, w)) for i in range(n)]


@dsl("transformation", ["grid", "size"], "list[grid]")
def vsplit(grid, n):
    """grid 를 가로줄 n 등분(나머지는 앞쪽 조각이 흡수)."""
    h, w = len(grid) // n, len(grid[0])
    offset = len(grid) % n != 0
    return [crop(grid, (h * i + i * offset, 0), (h, w)) for i in range(n)]


@dsl("transformation", ["grid", "size"], "grid", effect=effect("upscale", "grid"))
def hupscale(grid, factor):
    """각 셀을 가로로 factor 배 늘린다."""
    return [[v for v in row for _ in range(factor)] for row in grid]


@dsl("transformation", ["grid", "size"], "grid", effect=effect("upscale", "grid"))
def vupscale(grid, factor):
    """각 행을 세로로 factor 배 늘린다."""
    return [row[:] for row in grid for _ in range(factor)]


@dsl("transformation", ["grid", "size"], "grid", effect=effect("upscale", "grid"))
def upscale(element, factor):
    """grid 또는 object 를 가로세로 factor 배 확대(원본 arc-dsl 은 Element = Grid|Object)."""
    if isinstance(element, list):
        return [[v for v in row for _ in range(factor)] for row in element for _ in range(factor)]
    if len(element) == 0:
        return frozenset()
    idx = toindices(element)
    di = -min(i for i, j in idx)
    dj = -min(j for i, j in idx)
    out = set()
    for v, (i, j) in element:
        ni, nj = i + di, j + dj
        for io in range(factor):
            for jo in range(factor):
                out.add((v, (ni * factor + io - di, nj * factor + jo - dj)))
    return frozenset(out)


@dsl("transformation", ["grid", "size"], "grid", effect=effect("downscale", "grid"))
def downscale(grid, factor):
    """factor 간격으로 행/열을 골라 축소."""
    cols = [[v for j, v in enumerate(row) if j % factor == 0] for row in grid]
    return [row for i, row in enumerate(cols) if i % factor == 0]


# 판단: cellwise 는 a 를 기준으로 b 와 다른 셀만 fallback 으로 "채우는" 연산이라
# fill 버킷(effect("fill","grid"))으로 분류 — a,b 둘 다 grid 지만 결과는 a 형태의 새 grid.
@dsl("transformation", ["grid", "grid", "color"], "grid", effect=effect("fill", "grid"))
def cellwise(a, b, fallback):
    """a,b 를 셀별로 비교 — 같으면 a 값, 다르면 fallback."""
    return [[av if av == bv else fallback for av, bv in zip(ra, rb)] for ra, rb in zip(a, b)]


@dsl("transformation", ["color", "size"], "grid", effect=effect("create", "grid"))
def canvas(value, dims):
    """value 색으로 채운 dims=(h,w) 크기의 새 grid."""
    return [[value] * dims[1] for _ in range(dims[0])]


# 판단: normalize 는 patch(object)를 원점으로 옮기는 patch-level 헬퍼 — grid 자체를
# 바꾸지 않으므로 effect=None.
@dsl("transformation", ["object"], "object")
def normalize(patch):
    """patch 의 좌상단을 원점(0,0)으로 옮긴다."""
    idx = toindices(patch)
    if not idx:
        return patch
    di = -min(i for i, j in idx)
    dj = -min(j for i, j in idx)
    first = next(iter(patch))
    if isinstance(first[1], tuple):
        return frozenset((v, (i + di, j + dj)) for v, (i, j) in patch)
    return frozenset((i + di, j + dj) for i, j in patch)


# 판단: toobject/asobject 는 grid→object 변환 헬퍼(읽기, grid 를 바꾸지 않음) → effect=None.
@dsl("transformation", ["object", "grid"], "object")
def toobject(patch, grid):
    """patch 좌표에 grid 의 실제 색을 입혀 object 로."""
    H, W = len(grid), len(grid[0])
    return frozenset((grid[i][j], (i, j)) for i, j in toindices(patch) if 0 <= i < H and 0 <= j < W)


@dsl("transformation", ["grid"], "object")
def asobject(grid):
    """grid 전체를 object(모든 셀의 (색,좌표))로."""
    return frozenset((v, (i, j)) for i, row in enumerate(grid) for j, v in enumerate(row))
