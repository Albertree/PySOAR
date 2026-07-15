# -*- coding: utf-8 -*-
"""arc-dsl(michaelhodel) GRID transform 어휘 vendoring — list[list] 표현.
frozen 원자(make_grid/coloring)와 분리된 확장 어휘. propose 는 effect 일치로 걸린다."""
from procedural_memory.dsl.registry import dsl
from procedural_memory.dsl.effect import effect


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
