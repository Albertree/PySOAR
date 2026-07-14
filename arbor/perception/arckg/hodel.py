"""
hodel.py — Michael Hodel의 ARC DSL에서 object 추출에 필요한 함수만 최소 포팅.
원본: ARC-solver/DSL/base.py  (objects, dneighbors, neighbors, mostcolor, asindices)

외부 의존성 없이 순수 Python만 사용.
"""


def _mostcolor(grid: tuple) -> int:
    """격자에서 가장 많이 나타나는 색상 반환."""
    values = [v for row in grid for v in row]
    return max(set(values), key=values.count)


def _dneighbors(loc: tuple) -> frozenset:
    """상하좌우 4방향 인접 좌표."""
    r, c = loc
    return frozenset({(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)})


def _allneighbors(loc: tuple) -> frozenset:
    """4방향 + 대각선 8방향 인접 좌표."""
    r, c = loc
    return frozenset({
        (r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1),
        (r - 1, c - 1), (r - 1, c + 1), (r + 1, c - 1), (r + 1, c + 1),
    })


def hodel_objects(grid: tuple, univalued: bool,
                   diagonal: bool, without_bg: bool) -> frozenset:
    """
    Michael Hodel의 objects() 함수 포팅.
    격자에서 연결 성분을 찾아 frozenset of frozensets 반환.
    각 object: frozenset of (color, (row, col)) 쌍.

    Args:
        grid:        tuple[tuple[int]] — 읽기 전용 2D 격자
        univalued:   True → 동일 색상 픽셀만 같은 object로 묶음
        diagonal:    True → 대각선 방향도 연결로 취급
        without_bg:  True → 최다 색상(배경)을 object에서 제외
    """
    h, w = len(grid), len(grid[0])
    bg = _mostcolor(grid) if without_bg else None
    neighborfun = _allneighbors if diagonal else _dneighbors

    objs = set()
    occupied = set()

    for start_r in range(h):
        for start_c in range(w):
            loc = (start_r, start_c)
            if loc in occupied:
                continue
            val = grid[start_r][start_c]
            if val == bg:
                continue

            obj = {(val, loc)}
            cands = {loc}

            while cands:
                next_cands = set()
                for cand in cands:
                    v = grid[cand[0]][cand[1]]
                    if (val == v) if univalued else (v != bg):
                        obj.add((v, cand))
                        occupied.add(cand)
                        for nb in neighborfun(cand):
                            if 0 <= nb[0] < h and 0 <= nb[1] < w and nb not in occupied:
                                next_cands.add(nb)
                cands = next_cands

            objs.add(frozenset(obj))

    return frozenset(objs)


# 8가지 파라미터 조합 — 원본 object_finder.py find_all_objects 순서 그대로
PARAM_COMBINATIONS = [
    (True,  True,  True),   # univalued, diagonal, without_bg
    (False, True,  True),
    (True,  False, True),
    (False, False, True),
    (True,  True,  False),
    (False, True,  False),
    (True,  False, False),
    (False, False, False),
]


def find_all_objects(raw: list) -> list:
    """
    8가지 파라미터 조합으로 hodel_objects를 실행해 고유 object 목록을 반환.

    반환: list of dict, 각 dict:
        {
          "obj":    frozenset of (color, (row, col)),
          "pos":    (row_min, col_min),            ← left_top 절대 좌표
          "color":  {0: bool, ..., 9: bool},
          "method": {"univalued": bool, "diagonal": bool, "without_bg": bool},
          "colorgrid": list[list[int]],           ← bbox 크기, 투명=13
        }
    """
    grid = tuple(tuple(row) for row in raw)
    seen: set = set()
    result: list = []

    for univalued, diagonal, without_bg in PARAM_COMBINATIONS:
        for obj_fs in hodel_objects(grid, univalued, diagonal, without_bg):
            key = frozenset(obj_fs)
            if key in seen:
                continue
            seen.add(key)

            pixels = sorted(obj_fs, key=lambda x: (x[1][0], x[1][1]))
            rows = [r for _, (r, _) in pixels]
            cols = [c for _, (_, c) in pixels]
            row_min, row_max = min(rows), max(rows)
            col_min, col_max = min(cols), max(cols)

            bb_h = row_max - row_min + 1
            bb_w = col_max - col_min + 1
            colorgrid = [[13] * bb_w for _ in range(bb_h)]
            color_dict = {i: False for i in range(10)}
            for color, (r, c) in pixels:
                colorgrid[r - row_min][c - col_min] = color
                if 0 <= color <= 9:
                    color_dict[color] = True

            result.append({
                "obj":       frozenset(obj_fs),
                "pos":       (row_min, col_min),
                "color":     color_dict,
                "method":    {
                    "univalued":   univalued,
                    "diagonal":    diagonal,
                    "without_bg":  without_bg,
                },
                "colorgrid": colorgrid,
            })

    return result
