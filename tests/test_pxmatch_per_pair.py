# -*- coding: utf-8 -*-
"""
Task 1 (Part B enabler): PIXEL compare(pxmatch)가 focus 의 첫 pair 만이 아니라 **모든 train pair**
마다 실행되어, 각 pair 의 `{pair}.E_G0Xi-G1Xi` color-DIFF pixel relation 이 WM 에 남는지 검증.

BASE(수정 전): pxmatch cmp 가 focus group(첫 pair 의 pixel)에서만 grid 를 뽑아 **한 pair 분만**
compare 되므로, P1(변화 있는 두번째 train pair)의 pixel relation 이 WM 에 없다 → 이 테스트는 FAIL.
수정 후: grid `within` 분기처럼 G0·G1 이 모두 있는 **모든 train pair** 에 대해 pxmatch cmp 를 깔아
compare 가 각각 소비 → P0·P1 모두 relation 이 생긴다 → PASS.

run:  PYTHONHASHSEED=0 python -m pytest tests/test_pxmatch_per_pair.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.env.dataset import list_tasks, load_task              # noqa: E402
from debugger.solve_cache import run_solve                       # noqa: E402


def _changed_cells(pair):
    inp, out = pair["input"], pair["output"]
    H, W = len(inp), len(inp[0])
    return {(r, c) for r in range(H) for c in range(W) if inp[r][c] != out[r][c]}


def test_pxmatch_runs_for_every_train_pair():
    tasks = dict(list_tasks("move"))
    tid = "move000a"
    task = load_task(tasks[tid])
    wm = run_solve(tid, task, use_cache=False, mode="score")["wm"]
    wm_tuples = [tuple(t) for t in wm]

    for pidx, pair in enumerate(task["train"]):
        want = _changed_cells(pair)
        if not want:
            continue                                    # 변화 없는 pair 는 pixel DIFF relation 이 없어도 됨
        p = f"T{tid}.P{pidx}"
        # 이 pair(LCA=p) 아래 걸린 relation 중 pixel-level color DIFF (E_G0X..-G1X..) 만 추림.
        rel_ids = [v for (i, a, v) in wm_tuples
                   if i == p and a == "relation" and v.startswith(f"{p}.E_G0X")]
        assert rel_ids, f"{p}: pixel(E_G0Xi-G1Xi) relation 이 WM 에 없음 (pxmatch 가 이 pair 에서 안 돔)"
        for rid in rel_ids:
            assert (rid, "type", "DIFF") in wm_tuples, f"{rid}: type=DIFF 아님"
            color_node = f"{rid}.category.color"
            assert (color_node, "type", "DIFF") in wm_tuples, f"{rid}: category.color DIFF 아님"
        assert len(rel_ids) == len(want), (
            f"{p}: pixel DIFF relation 개수({len(rel_ids)}) != raw 변화셀 수({len(want)}) — "
            f"relations={sorted(rel_ids)} want={sorted(want)}")


if __name__ == "__main__":
    test_pxmatch_runs_for_every_train_pair()
    print("ok  test_pxmatch_runs_for_every_train_pair")
