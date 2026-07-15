# -*- coding: utf-8 -*-
"""arc-dsl(michaelhodel) 인덱스집합/객체 어휘 vendoring — list[list] 표현.

두 갈래:
  · WRAP  — objects/partition/fgpartition: 실제 객체 탐색은 ARCKG 의
    `arbor.perception.arckg.hodel.find_all_objects` 를 재사용한다(§2-1, 재구현 금지).
    partition/fgpartition 은 원본 arc-dsl 에서 "같은 색 셀 전부"(연결성 무관)를 한 object 로
    묶는 연산이라 find_all_objects 의 연결-성분 기반 결과로는 못 만든다 — 그 그룹핑 루프만
    직접 포팅하되, 배경색 판정은 hodel.py 의 `_mostcolor` 를 그대로 재사용(중복 구현 회피).
  · VENDOR — 좌표/인덱스집합 순수 함수(box, corners, backdrop, delta, neighbors, connect, …)는
    arc-dsl 원본 body 를 tuple→list/frozenset 표현으로 그대로 이식.

읽기 전용(탐색/선택)이라 전부 effect=None(디폴트) — dsl 데코레이터에 effect 인자를 안 준다.
transformation(hodel_transforms.py)·relation(hodel_relation.py) 양쪽이 여기 `toindices` 를
빌려 쓴다(selection/__init__.py 서두 docstring: "relation·transformation 양쪽이 빌려 쓰므로
독립 카테고리" — 그 재료가 바로 이 모듈의 인덱스집합 함수들이다).
"""
from procedural_memory.dsl.registry import dsl
from arbor.perception.arckg.hodel import find_all_objects, _mostcolor


# ── toindices — patch(= object cells 또는 순수 indices) 를 순수 indices 로 ──
@dsl("selection", ["object"], "indices")
def toindices(patch):
    """patch 가 (color,(i,j)) 쌍의 object 면 좌표만 뽑고, 이미 (i,j) 순수 indices 면 그대로."""
    if len(patch) == 0:
        return frozenset()
    first = next(iter(patch))
    if isinstance(first[1], tuple):
        return frozenset(index for _, index in patch)
    return patch


def _bbox(patch):
    """patch(object/indices) 의 (ui, uj, li, lj) — upper-left/lower-right corner."""
    idx = toindices(patch)
    rows = [i for i, j in idx]
    cols = [j for i, j in idx]
    return min(rows), min(cols), max(rows), max(cols)


@dsl("selection", ["grid"], "indices")
def asindices(grid):
    """grid 전체 셀 좌표."""
    return frozenset((i, j) for i in range(len(grid)) for j in range(len(grid[0])))


@dsl("selection", ["grid", "color"], "indices")
def ofcolor(grid, value):
    """grid 에서 value 색인 셀 좌표."""
    return frozenset((i, j) for i, row in enumerate(grid) for j, v in enumerate(row) if v == value)


@dsl("selection", ["position"], "indices")
def dneighbors(loc):
    """상하좌우 4방향 인접 좌표."""
    i, j = loc
    return frozenset({(i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)})


@dsl("selection", ["position"], "indices")
def ineighbors(loc):
    """대각 4방향 인접 좌표."""
    i, j = loc
    return frozenset({(i - 1, j - 1), (i - 1, j + 1), (i + 1, j - 1), (i + 1, j + 1)})


@dsl("selection", ["position"], "indices")
def neighbors(loc):
    """8방향 인접 좌표."""
    return dneighbors(loc) | ineighbors(loc)


@dsl("selection", ["position", "position"], "indices")
def connect(a, b):
    """두 점을 잇는 직선(수평/수직/대각) 좌표. 직선이 아니면 빈 집합."""
    ai, aj = a
    bi, bj = b
    si, ei = min(ai, bi), max(ai, bi) + 1
    sj, ej = min(aj, bj), max(aj, bj) + 1
    if ai == bi:
        return frozenset((ai, j) for j in range(sj, ej))
    if aj == bj:
        return frozenset((i, aj) for i in range(si, ei))
    if bi - ai == bj - aj:
        return frozenset((i, j) for i, j in zip(range(si, ei), range(sj, ej)))
    if bi - ai == aj - bj:
        return frozenset((i, j) for i, j in zip(range(si, ei), range(ej - 1, sj - 1, -1)))
    return frozenset()


@dsl("selection", ["position", "position"], "indices")
def shoot(start, direction):
    """start 에서 direction 으로 뻗어나가는 직선(길이 42, arc-dsl 원본과 동일한 한도)."""
    di, dj = direction
    return connect(start, (start[0] + 42 * di, start[1] + 42 * dj))


@dsl("selection", ["grid"], "list[object]")
def frontiers(grid):
    """grid 전체를 관통하는 단색 행/열(frontier) 들."""
    h, w = len(grid), len(grid[0])
    cols = list(zip(*grid))
    row_idx = [i for i, r in enumerate(grid) if len(set(r)) == 1]
    col_idx = [j for j, c in enumerate(cols) if len(set(c)) == 1]
    hf = frozenset(frozenset((grid[i][j], (i, j)) for j in range(w)) for i in row_idx)
    vf = frozenset(frozenset((grid[i][j], (i, j)) for i in range(h)) for j in col_idx)
    return hf | vf


@dsl("selection", ["list[object]", "color"], "list[object]")
def colorfilter(objs, value):
    """color 가 value 인 object 만."""
    return frozenset(obj for obj in objs if next(iter(obj))[0] == value)


@dsl("selection", ["list[object]", "int"], "list[object]")
def sizefilter(container, n):
    """크기(셀 수)가 n 인 항목만."""
    return frozenset(item for item in container if len(item) == n)


@dsl("selection", ["object"], "indices")
def box(patch):
    """patch bbox 의 외곽선(테두리) 좌표."""
    if len(patch) == 0:
        return patch
    ai, aj, bi, bj = _bbox(patch)
    vlines = {(i, aj) for i in range(ai, bi + 1)} | {(i, bj) for i in range(ai, bi + 1)}
    hlines = {(ai, j) for j in range(aj, bj + 1)} | {(bi, j) for j in range(aj, bj + 1)}
    return frozenset(vlines | hlines)


@dsl("selection", ["object"], "indices")
def corners(patch):
    """patch bbox 네 모서리 좌표."""
    ai, aj, bi, bj = _bbox(patch)
    return frozenset({(ai, aj), (ai, bj), (bi, aj), (bi, bj)})


@dsl("selection", ["object"], "indices")
def backdrop(patch):
    """patch bbox 안의 모든 좌표(patch 밖 셀 포함)."""
    if len(patch) == 0:
        return frozenset()
    ai, aj, bi, bj = _bbox(patch)
    return frozenset((i, j) for i in range(ai, bi + 1) for j in range(aj, bj + 1))


@dsl("selection", ["object"], "indices")
def delta(patch):
    """patch bbox 안이지만 patch 에는 없는 좌표."""
    if len(patch) == 0:
        return frozenset()
    return backdrop(patch) - toindices(patch)


@dsl("selection", ["grid", "object"], "indices")
def occurrences(grid, obj):
    """grid 안에서 obj(색 포함 패턴)가 정확히 일치하는 모든 좌상단 위치."""
    if len(obj) == 0:
        return frozenset()
    ai, aj, bi, bj = _bbox(obj)
    normed = frozenset((v, (i - ai, j - aj)) for v, (i, j) in obj)
    h, w = len(grid), len(grid[0])
    oh, ow = bi - ai + 1, bj - aj + 1
    occs = set()
    for i in range(h - oh + 1):
        for j in range(w - ow + 1):
            ok = True
            for v, (di, dj) in normed:
                if grid[i + di][j + dj] != v:
                    ok = False
                    break
            if ok:
                occs.add((i, j))
    return frozenset(occs)


# ── WRAP: objects/partition/fgpartition ──────────────────────────────────
@dsl("selection", ["grid"], "list[object]")
def objects(grid):
    """grid 의 모든 연결-객체(8 param 조합) — ARCKG find_all_objects 재사용(§2-1)."""
    return [d["obj"] for d in find_all_objects(grid)]


def _partition_by_color(grid, colors):
    return [frozenset((v, (i, j)) for i, row in enumerate(grid) for j, v in enumerate(row) if v == value)
            for value in colors]


@dsl("selection", ["grid"], "list[object]")
def partition(grid):
    """grid 를 색별로 파티션(연결성 무관 — 같은 색 셀 전부가 한 object)."""
    colors = {v for row in grid for v in row}
    return _partition_by_color(grid, colors)


@dsl("selection", ["grid"], "list[object]")
def fgpartition(grid):
    """partition 과 같되 배경색(최다색) 제외. 배경 판정은 hodel.py `_mostcolor` 재사용."""
    bg = _mostcolor(tuple(tuple(r) for r in grid))
    colors = {v for row in grid for v in row} - {bg}
    return _partition_by_color(grid, colors)
