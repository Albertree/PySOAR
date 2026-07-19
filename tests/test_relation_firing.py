# -*- coding: utf-8 -*-
# tests/test_relation_firing.py — Part B relation 발화 스모크(최소)
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve


def _wm(ds, tid):
    return run_solve(tid, load_task(dict(list_tasks(ds))[tid]), use_cache=False, mode="score")["wm"]


def test_no_xform_symbol_anywhere():
    for ds, tid in [("move", "move000a"), ("agi", "08ed6ac7")]:
        wm = _wm(ds, tid)
        for (i, a, v) in wm:
            assert a not in ("xform", "g0cells", "g1color") and ".xform." not in i, f"{tid}: {i} ^{a}"


def test_pixel_relation_firing_move():
    wm = _wm("move", "move000a")
    assert any(a == "recolor-rel" for (i, a, v) in wm)          # pixel 이 relation 발화


def test_object_relations_per_pair_08ed():
    wm = _wm("agi", "08ed6ac7")
    pairs = {v.split(".")[1] for (i, a, v) in wm if a == "relation" and ".E_G0O" in v}
    assert len(pairs) >= 2                                     # per-pair object 관계 존재
