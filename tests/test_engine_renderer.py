import os, pickle
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve

_GOLD = pickle.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "engine_golden.pkl"), "rb"))
_PATHS = {tid: p for ds in ("easy_a", "move") for tid, p in list_tasks(ds)}


def _run(tid):
    return run_solve(tid, load_task(_PATHS[tid]), max_cycles=500, use_cache=False)


def test_debug_output_matches_golden():
    for tid, g in _GOLD.items():
        r = _run(tid)
        assert r["events"] == g["events"], f"{tid} events 불일치"
        assert r["wm_states"] == g["wm_states"], f"{tid} wm_states 불일치"


def test_score_mode_same_attempts_as_debug():
    for tid in _GOLD:
        t = load_task(_PATHS[tid])
        deb = run_solve(tid, t, max_cycles=500, use_cache=False, mode="debug")
        sco = run_solve(tid, t, max_cycles=500, use_cache=False, mode="score")
        assert [a["correct"] for a in sco["attempts"]] == [a["correct"] for a in deb["attempts"]]
        assert sco["events"] == [] and sco["wm_states"] == []
