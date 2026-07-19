# -*- coding: utf-8 -*-
"""Spelke Core Object Perception 기반 객체 검출 (실험 — spelke-object-detection 브랜치).

영아 인지(Spelke)의 4원리를 grid 객체 검출에 매핑한다:
  · Cohesion(응집성)   : 객체는 하나의 연결된 표면 덩어리 → 4-연결(접촉)이 객체성의 1차 기준.
  · Boundedness(경계성): 객체는 뚜렷한 경계 → 색이 바뀌는 지점이 경계. 같은 색으로 연결된 최대
                         영역 = 경계로 둘러싸인 한 객체. (이동 후 배경색이 된 잔여셀은 배경에
                         '흡수'돼 독립 경계가 없다 = figure 아님.)
  · Rigidity(강체성)         : 형태 유지하며 이동 — **프레임 간** 대응 원리(단일 grid 검출엔 무관).
  · No action at a distance : 접촉 없이는 영향 없음 — **객체 간 상호작용** 원리(단일 grid 검출엔 무관).

따라서 단일 grid 의 '객체 리스트' 검출 = Cohesion + Boundedness = **4-연결 동색 성분**.
배경을 count/max 로 특권화하지 않는다(§no-arbitrary-filters). 추가로 Boundedness 로 각 성분을
figure(단일색에 둘러싸임) / ground(격자 테두리에 닿는 감싸는 표면)로 **분류**만 한다(리스트는 불변).
"""
from __future__ import annotations


def _cohesion_components(grid):
    """Cohesion: 4-연결된 동색 셀 = 한 표면. 모든 성분 [(cells, color)] (배경 특권화 없음)."""
    H, W = len(grid), len(grid[0])
    seen, objs = set(), []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen:
                continue
            col, stack, cells = grid[r][c], [(r, c)], []
            while stack:
                y, x = stack.pop()
                if (y, x) in seen or not (0 <= y < H and 0 <= x < W) or grid[y][x] != col:
                    continue
                seen.add((y, x)); cells.append((y, x))
                stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
            objs.append((sorted(cells), col))
    return objs


def _boundary_colors(cells, grid):
    """Boundedness: 이 성분을 둘러싼(4-이웃, 성분 밖) 색 집합. 격자 테두리 접촉 여부도."""
    H, W = len(grid), len(grid[0])
    cset = set(cells)
    adj, touches_edge = set(), False
    for (r, c) in cells:
        if r in (0, H - 1) or c in (0, W - 1):
            touches_edge = True
        for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= nb[0] < H and 0 <= nb[1] < W and nb not in cset:
                adj.add(grid[nb[0]][nb[1]])
    return adj, touches_edge


def _same_color_8conn(grid):
    """같은 색끼리 **8-연결(대각 포함)** 성분 — 4-conn 기본 위의 '적당히 묶은' 계층.
    색 경계는 안 넘고(hodel multi 과잉병합 회피), 배경도 안 뺀다(count/max 없음)."""
    H, W = len(grid), len(grid[0])
    seen, objs = set(), []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen:
                continue
            col, stack, cells = grid[r][c], [(r, c)], []
            while stack:
                y, x = stack.pop()
                if (y, x) in seen or not (0 <= y < H and 0 <= x < W) or grid[y][x] != col:
                    continue
                seen.add((y, x)); cells.append((y, x))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dy or dx:
                            stack.append((y + dy, x + dx))     # 8-이웃(대각 포함)
            objs.append((sorted(cells), col))
    return objs


def object_hierarchy(grid):
    """spelke 2계층 객체 뷰 — 탐색공간을 필요에 맞게 줄이는 후보 계층.
      fine  : 4-conn 동색 (spelke 기본, 가장 보수적)
      group : 8-conn 동색 (같은 색 대각선 응집을 한 덩어리로 — 선/윤곽 회복). fine 의 상위 묶음.
    반환 {"fine": [(cells,color)], "group": [(cells,color, [fine index들])]}.
    group 은 색을 안 넘고 배경도 안 빼므로 hodel 의 다색/no-bg 과잉병합을 피한다."""
    fine = sorted(_cohesion_components(grid), key=lambda cc: (cc[0][0], cc[1]))
    fine_owner = {}
    for i, (cells, _col) in enumerate(fine):
        for rc in cells:
            fine_owner[rc] = i
    groups = []
    for cells, col in sorted(_same_color_8conn(grid), key=lambda cc: (cc[0][0], cc[1])):
        members = sorted({fine_owner[rc] for rc in cells})
        groups.append((cells, col, members))
    return {"fine": fine, "group": groups}


def spelke_union(grid):
    """spelke 객체 합집합 [(cells, color)] — 4-conn ∪ 같은색 8-conn (dedup). perception.objects_of
    가 반환하던 4-conn 리스트를 대체(디버거·DSL accessor 공용). 첫셀·색 정렬."""
    seen, out = set(), []
    for cells, col in _cohesion_components(grid) + _same_color_8conn(grid):
        k = frozenset(cells)
        if k in seen:
            continue
        seen.add(k); out.append((sorted(cells), col))
    return sorted(out, key=lambda cc: (cc[0][0], cc[1]))


def spelke_arckg_objects(raw):
    """ARCKG `grid.objects` 용 객체 검출 — **spelke 4-conn ∪ 같은색 8-conn 합집합**.
    hodel `find_all_objects` 를 대체(동일 반환 format). 셀집합으로 dedup(4-conn 과 8-conn 이 같으면
    하나만; 8-conn 이 대각선으로 여럿을 묶으면 그 묶음이 fine 조각들 위에 추가).
    반환: list of dict {obj: frozenset((color,(r,c))), pos, color(presence dict), colorgrid(bbox·투명13)}.
    count/max·배경특권화 없음(§no-arbitrary-filters)."""
    fine = _cohesion_components(raw)                       # (cells, color) 4-conn 동색
    group = _same_color_8conn(raw)                         # (cells, color) 8-conn 동색
    seen, out = set(), []
    for cells, col in fine + group:
        key = frozenset(cells)
        if key in seen:                                   # 4-conn==8-conn 이면 한 번만(fine 우선)
            continue
        seen.add(key)
        pixels = sorted(((col, (r, c)) for (r, c) in cells), key=lambda x: (x[1][0], x[1][1]))
        rows = [p[1][0] for p in pixels]; cols = [p[1][1] for p in pixels]
        rmin, rmax, cmin, cmax = min(rows), max(rows), min(cols), max(cols)
        cg = [[13] * (cmax - cmin + 1) for _ in range(rmax - rmin + 1)]
        color_dict = {i: False for i in range(10)}
        for c_, (r, cc) in pixels:
            cg[r - rmin][cc - cmin] = c_
            if 0 <= c_ <= 9:
                color_dict[c_] = True
        out.append({"obj": frozenset(pixels), "pos": (rmin, cmin), "color": color_dict,
                    "colorgrid": cg})
    return out


def objects_of_spelke(grid, classify=False):
    """Spelke(Cohesion+Boundedness) 객체 검출. classify=False 면 현행 objects_of 와 **동일 형식**
    [(cells, color)] 을 같은 정렬로 반환(대체 후보). classify=True 면 각 성분에 role 태그를 붙여
    [(cells, color, role)] 반환 — role='figure'(단일색에 둘러싸인 경계객체) / 'ground'(감싸는 표면)."""
    objs = _cohesion_components(grid)
    if not classify:
        return sorted(objs, key=lambda cc: (cc[0][0], cc[1]))
    tagged = []
    for cells, col in objs:
        adj, edge = _boundary_colors(cells, grid)
        # figure = 단일색에 둘러싸임(뚜렷한 경계). ground = 여러 색과 접하며 테두리에 닿는 감싸는 표면.
        role = "figure" if (len(adj) == 1 and not (edge and len(adj) > 1)) else "ground"
        if len(adj) >= 2:
            role = "ground"
        tagged.append((sorted(cells), col, role))
    return sorted(tagged, key=lambda cc: (cc[0][0], cc[1]))
