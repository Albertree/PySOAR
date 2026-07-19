# -*- coding: utf-8 -*-
"""
Task 3a (Part B enabler): OBJECT compare(match)가 focus 의 첫 train pair 만이 아니라 **모든 train
pair** 마다 실행되어, 각 pair 의 `{pair}.E_G0Oi-G1Oj` object relation 이 WM 에 남는지 검증.

BASE(수정 전): `_build_agenda` 의 `elif kind == "object":` 분기가 `train[0]`(첫 pair) 하나만
cmp:match 를 깔아 compare 하므로, 08ed6ac7 의 두 train pair 중 P1 의 object relation 이 WM 에
없다 → 이 테스트는 FAIL. 수정 후: grid `within` 분기처럼 G0·G1 이 모두 있는 **모든 train pair**
에 대해 cmp:match 를 깔아 compare 가 각각 소비 → P0·P1 모두 relation 이 생긴다 → PASS.

run:  PYTHONHASHSEED=0 python -m pytest tests/test_object_match_per_pair.py -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.env.dataset import list_tasks, load_task              # noqa: E402
from debugger.solve_cache import run_solve                       # noqa: E402


def test_object_match_runs_for_every_train_pair():
    tid = "08ed6ac7"
    task = load_task(dict(list_tasks("agi"))[tid])
    wm = run_solve(tid, task, use_cache=False, mode="score")["wm"]
    wm_tuples = [tuple(t) for t in wm]

    n_train = len(task["train"])
    assert n_train == 2, f"이 테스트는 08ed6ac7 이 train pair 2개라고 가정(실제 {n_train})"

    for pidx in range(n_train):
        p = f"T{tid}.P{pidx}"
        # 이 pair(LCA=p) 아래 걸린 relation 중 object-level match (E_G0O..-G1O..) 만 추림.
        rel_ids = [v for (i, a, v) in wm_tuples
                   if i == p and a == "relation" and v.startswith(f"{p}.E_G0O")]
        assert rel_ids, f"{p}: object(E_G0Oi-G1Oj) relation 이 WM 에 없음 (match 가 이 pair 에서 안 돔)"


if __name__ == "__main__":
    test_object_match_runs_for_every_train_pair()
    print("ok  test_object_match_runs_for_every_train_pair")
