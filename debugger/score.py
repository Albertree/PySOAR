# -*- coding: utf-8 -*-
"""arc_human/<dataset> 채점 — run_solve(mode='score') 빠른 경로(방출·스냅샷 0)로 전 태스크 solve.

    python -m debugger.score move        # -> SCORE: n/total

회귀·스케일링용(정오만 빠르게). 시각화 대시보드는 debugger.build(mode='debug')."""
from __future__ import annotations
import sys
import time
from arbor.env.dataset import list_tasks, load_task
from debugger.solve_cache import run_solve


def score_dataset(dataset, limit=None, max_cycles=500, use_cache=False):
    """dataset 전 태스크(또는 limit 개)를 score 모드로 solve → {ok, total, fail, seconds}."""
    tasks = [(tid, load_task(p)) for tid, p in list_tasks(dataset, limit=limit)]
    ok, fail = 0, []
    t0 = time.time()
    for tid, t in tasks:
        r = run_solve(tid, t, max_cycles=max_cycles, use_cache=use_cache, mode="score")
        if any(a["correct"] for a in r["attempts"]):
            ok += 1
        else:
            fail.append(tid)
    return {"ok": ok, "total": len(tasks), "fail": fail, "seconds": time.time() - t0}


def main(argv):
    dataset = argv[1] if len(argv) > 1 else "move"
    r = score_dataset(dataset)
    print(f"SCORE: {r['ok']}/{r['total']}  ({r['seconds']:.1f}s, "
          f"{r['seconds'] / max(r['total'], 1):.2f}s/task)")
    if r["fail"]:
        print("FAIL:", r["fail"])


if __name__ == "__main__":
    main(sys.argv)
