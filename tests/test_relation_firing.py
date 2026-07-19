# -*- coding: utf-8 -*-
# tests/test_relation_firing.py — Part B relation 발화 스모크(move 60 기준만).
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve


def _wm(ds, tid):
    return run_solve(tid, load_task(dict(list_tasks(ds))[tid]), use_cache=False, mode="score")["wm"]


def test_no_xform_symbol_move():
    # xform/g0cells/g1color 심볼이 완전히 사라졌다(coloring 은 compare relation 직결).
    wm = _wm("move", "move000a")
    for (i, a, v) in wm:
        assert a not in ("xform", "g0cells", "g1color") and ".xform." not in i, f"{i} ^{a}"


def test_pixel_relation_firing_move():
    # PIXEL coloring 이 pixel compare relation(recolor-rel)에서 발화한다.
    wm = _wm("move", "move000a")
    assert any(a == "recolor-rel" for (i, a, v) in wm)
