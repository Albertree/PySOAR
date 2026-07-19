# -*- coding: utf-8 -*-
"""
Task 2 (Part B): PIXEL coloring 이 xform 없이 **pixel compare relation**(`{pair}.E_G0Xi-G1Xi`,
category.color=DIFF, category.coordinate=COMM)만으로 발화·색칠하는지 검증. WM 구조는 task-2-brief.md
실측(§pixel relation WM 구조) 을 손으로 재현한다.

BASE(수정 전) `_op_coloring` 는 `sid ^recolor-rel` 을 전혀 안 읽는다(그 시절 PIXEL 은 xform 을 스스로
만들었다) — 그래서 `sid ^sim`/`sid ^program-code` 가 변화 없이 그대로이므로 이 테스트는 BASE 에서
FAIL 해야 정상이다.

run:  PYTHONHASHSEED=0 python -m pytest tests/test_coloring_from_pixel_rel.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Agent                                            # noqa: E402
from arbor.expr_solver import _tup                                 # noqa: E402
from procedural_memory.operators.coloring import _op_coloring       # noqa: E402


def _add_pixel_rel(ag, E, r, c, out):
    """task-2-brief.md 의 pixel relation WM 구조를 손으로 재현.
    (E,type=DIFF)(E,category,C)(C,color,col)(col,type=DIFF)(col,comp2,out)
    (C,coordinate,crd)(crd,category,cc)(cc,row_index,ri)(ri,comp1,r)(cc,col_index,ci)(ci,comp1,c)
    WM 값은 실제로도 문자열/정수 혼재 가능 — 여기선 브리프대로 문자열로 넣어 int() 변환 경로를 확인."""
    C, col, crd = f"{E}.category", f"{E}.category.color", f"{E}.category.coordinate"
    cc = f"{crd}.category"
    ri, ci = f"{cc}.row_index", f"{cc}.col_index"
    ag.wm.add(E, "type", "DIFF")
    ag.wm.add(E, "category", C)
    ag.wm.add(C, "color", col)
    ag.wm.add(col, "type", "DIFF")
    ag.wm.add(col, "comp2", str(out))
    ag.wm.add(C, "coordinate", crd)
    ag.wm.add(crd, "category", cc)
    ag.wm.add(cc, "row_index", ri)
    ag.wm.add(ri, "comp1", str(r))
    ag.wm.add(cc, "col_index", ci)
    ag.wm.add(ci, "comp1", str(c))


def _step_target_coord(step):
    a = step["args"]["target"]
    return a["ref"], tuple(a["index"]["const"])


def test_pixel_relation_colors_and_emits_program_steps():
    ag = Agent([])
    sid = ag.stack[-1].id          # "S1" (top state — 셀만 있으면 되니 substate 안 만듦)

    grid = [[0, 0, 0, 0] for _ in range(4)]     # 4x4, W=4
    ag.wm.add(sid, "sim", _tup(grid))

    # 두 relation: 라스터 순서(r*W+c)가 뒤바뀌게 넣어 byte-safe 정렬(오름차순) 확인.
    E_late = "Tt.P0.E_G0X14-G1X14"    # r=3,c=2 -> idx 14
    E_early = "Tt.P0.E_G0X0-G1X0"     # r=0,c=0 -> idx 0
    _add_pixel_rel(ag, E_late, 3, 2, 5)
    _add_pixel_rel(ag, E_early, 0, 0, 7)
    ag.wm.add(sid, "recolor-rel", E_late)
    ag.wm.add(sid, "recolor-rel", E_early)

    _op_coloring(ag)

    sim_after = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    assert sim_after is not None
    grid_after = [list(r) for r in sim_after]
    assert grid_after[0][0] == 7, f"(0,0) 이 comp2 색(7)으로 안 칠해짐: {grid_after}"
    assert grid_after[3][2] == 5, f"(3,2) 이 comp2 색(5)으로 안 칠해짐: {grid_after}"
    # 나머지 셀은 안 건드림
    grid_after[0][0] = grid_after[3][2] = 0
    assert grid_after == [[0, 0, 0, 0] for _ in range(4)]

    assert (E_late, "colored", "yes") in [tuple(t) for t in ag.wm]
    assert (E_early, "colored", "yes") in [tuple(t) for t in ag.wm]

    import json
    prog_code = next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), None)
    assert prog_code is not None, "sid ^program-code 가 안 남음"
    ast = json.loads(prog_code)
    body = ast["body"]
    coord_steps = [s for s in body if s.get("call") == "coloring"]
    assert len(coord_steps) == 2
    targets = [_step_target_coord(s) for s in coord_steps]
    assert targets == [("coord", (0, 0)), ("coord", (3, 2))], (
        f"raster order(r*W+c 오름차순) 로 안 나옴: {targets}")
    colors = [s["args"]["color"]["const"] for s in coord_steps]
    assert colors == [7, 5]

    assert (sid, "colored-all", "yes") in [tuple(t) for t in ag.wm]


if __name__ == "__main__":
    test_pixel_relation_colors_and_emits_program_steps()
    print("ok  test_pixel_relation_colors_and_emits_program_steps")
