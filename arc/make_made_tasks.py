# -*- coding: utf-8 -*-
"""
make_made_tasks -- 워크스루의 문제 A/B 를 실제 ARC 태스크(made000a/made000b)로
생성해 arc/data/made/ 에 저장한다. 셀 목록으로만 격자를 짜서(하드코딩 오류 방지)
JSON 으로 굳힌다.

  made000a : 문제 A -- "area 가 가장 큰 object 의 색"을 1×1 로 출력.
             (compare→refine→aggregate 로 '가장 큰'을 도출하는 게 요점)
  made000b : 문제 B -- object 를 grid 의 우하단 코너로 이동(translation).
             (align/resolve/invent 가 필요한 변환형)

run:  python3 arc/make_made_tasks.py
"""
from __future__ import annotations

import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "made")


def grid(h, w, cells, bg=0):
    """cells: {(r,c): color}. 나머지는 bg."""
    g = [[bg] * w for _ in range(h)]
    for (r, c), v in cells.items():
        g[r][c] = v
    return g


def block(r0, c0, h, w, color):
    return {(r0 + dr, c0 + dc): color for dr in range(h) for dc in range(w)}


def cellset(coords, color):
    return {(r, c): color for (r, c) in coords}


# ---------------------------------------------------------------------------
# made000a -- "가장 큰(area) object 의 색" → 1×1
#   P0: 파랑1(area6) · 초록3(4) · 빨강2(3)         → [[1]]
#   P1: 하늘8(area7) · 노랑4(2) · 보라5(5)          → [[8]]
#   Pa: 자홍6(area9) · 빨강2(5) · 초록3(3)          → [[6]]
# ---------------------------------------------------------------------------
def made000a():
    p0 = {**block(0, 1, 2, 3, 1), **block(3, 5, 2, 2, 3),           # 파랑6, 초록4
          **cellset([(6, 0), (6, 1), (7, 0)], 2)}                    # 빨강3
    p1 = {**cellset([(3, 3), (3, 4), (3, 5), (4, 3), (4, 4), (4, 5), (5, 4)], 8),  # 하늘7
          **cellset([(0, 1), (0, 2)], 4),                            # 노랑2
          **cellset([(1, 7), (2, 7), (3, 7), (4, 7), (5, 7)], 5)}    # 보라5
    pa = {**block(5, 1, 3, 3, 6),                                    # 자홍9
          **cellset([(0, 4), (0, 5), (1, 4), (1, 5), (2, 4)], 2),    # 빨강5
          **cellset([(6, 7), (7, 6), (7, 7)], 3)}                    # 초록3
    return {
        "train": [
            {"input": grid(8, 8, p0), "output": [[1]]},
            {"input": grid(8, 8, p1), "output": [[8]]},
        ],
        "test": [{"input": grid(8, 8, pa), "output": [[6]]}],
    }


# ---------------------------------------------------------------------------
# made000b -- object 를 grid 우하단 코너로 이동(translation)
#   P0: 6×6, 초록3 2×2 @ (1,1)  → 우하단 (4,4)
#   P1: 5×7, 노랑4 2×3 @ (1,2)  → 우하단 (3,4)
#   Pa: 8×8, 파랑1 3×2 @ (0,1)  → 우하단 (5,6)
# ---------------------------------------------------------------------------
def made000b():
    return {
        "train": [
            {"input": grid(6, 6, block(1, 1, 2, 2, 3)),
             "output": grid(6, 6, block(4, 4, 2, 2, 3))},
            {"input": grid(5, 7, block(1, 2, 2, 3, 4)),
             "output": grid(5, 7, block(3, 4, 2, 3, 4))},
        ],
        "test": [{"input": grid(8, 8, block(0, 1, 3, 2, 1)),
                  "output": grid(8, 8, block(5, 6, 3, 2, 1))}],
    }


def write_all():
    os.makedirs(DATA, exist_ok=True)
    for tid, fn in (("made000a", made000a), ("made000b", made000b)):
        path = os.path.join(DATA, f"{tid}.json")
        with open(path, "w") as f:
            json.dump(fn(), f)
        print(f"wrote {path}")


if __name__ == "__main__":
    write_all()
