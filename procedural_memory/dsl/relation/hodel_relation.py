# -*- coding: utf-8 -*-
"""arc-dsl(michaelhodel) 관계 어휘 vendoring — 두 patch/grid 사이의 관계(공통 행/열 여부,
거리, 인접, 상대 위치, 근접이동 방향). 원본 body 를 list/frozenset 표현으로 이식.

`toindices` 는 selection.hodel_selection 의 것을 재사용(§2-1 정신 — 좌표 추출 로직 중복
금지). relation 은 selection 뒤에 로드되므로(procedural_memory/dsl/__init__.py 순서:
util→property→transformation→selection→relation) 순환 import 가 없다.

전부 읽기 전용 비교라 effect=None(디폴트) — dsl 데코레이터에 effect 인자를 안 준다.
"""
from procedural_memory.dsl.registry import dsl
from procedural_memory.dsl.selection.hodel_selection import toindices


def _center(patch):
    idx = toindices(patch)
    rows = [i for i, j in idx]
    cols = [j for i, j in idx]
    ui, li = min(rows), max(rows)
    lj, rj = min(cols), max(cols)
    h, w = li - ui + 1, rj - lj + 1
    return ui + h // 2, lj + w // 2


def _shift_patch(patch, di, dj):
    if len(patch) == 0:
        return patch
    first = next(iter(patch))
    if isinstance(first[1], tuple):
        return frozenset((v, (i + di, j + dj)) for v, (i, j) in patch)
    return frozenset((i + di, j + dj) for i, j in patch)


@dsl("relation", ["object", "object"], "bool")
def hmatching(a, b):
    """두 patch 가 셀을 공유하는 행이 하나라도 있나."""
    return len({i for i, j in toindices(a)} & {i for i, j in toindices(b)}) > 0


@dsl("relation", ["object", "object"], "bool")
def vmatching(a, b):
    """두 patch 가 셀을 공유하는 열이 하나라도 있나."""
    return len({j for i, j in toindices(a)} & {j for i, j in toindices(b)}) > 0


@dsl("relation", ["object", "object"], "int")
def manhattan(a, b):
    """두 patch 사이 최단 맨해튼 거리."""
    ai = toindices(a)
    bi = toindices(b)
    return min(abs(x1 - x2) + abs(y1 - y2) for x1, y1 in ai for x2, y2 in bi)


@dsl("relation", ["object", "object"], "bool")
def adjacent(a, b):
    """두 patch 가 맞닿아 있나(맨해튼 거리 1)."""
    return manhattan(a, b) == 1


@dsl("relation", ["object", "grid"], "bool")
def bordering(patch, grid):
    """patch 가 grid 테두리에 닿아 있나."""
    idx = toindices(patch)
    rows = [i for i, j in idx]
    cols = [j for i, j in idx]
    return (min(rows) == 0 or min(cols) == 0
            or max(rows) == len(grid) - 1 or max(cols) == len(grid[0]) - 1)


@dsl("relation", ["object", "object"], "position")
def position(a, b):
    """a 기준 b 의 상대 위치(부호 벡터)."""
    ia, ja = _center(a)
    ib, jb = _center(b)
    if ia == ib:
        return (0, 1 if ja < jb else -1)
    if ja == jb:
        return (1 if ia < ib else -1, 0)
    if ia < ib:
        return (1, 1 if ja < jb else -1)
    return (-1, 1 if ja < jb else -1)


@dsl("relation", ["object", "object"], "position")
def gravitate(source, destination):
    """source 를 destination 에 맞닿을 때까지 옮기는 방향+거리."""
    si, sj = _center(source)
    di, dj = _center(destination)
    i, j = 0, 0
    if vmatching(source, destination):
        i = 1 if si < di else -1
    else:
        j = 1 if sj < dj else -1
    gi, gj = i, j
    c = 0
    while not adjacent(source, destination) and c < 42:
        c += 1
        gi += i
        gj += j
        source = _shift_patch(source, i, j)
    return (gi - i, gj - j)
