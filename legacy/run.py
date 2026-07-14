"""
run -- the ARC episode loop: REAL data -> 3-submit environment -> unified PySOAR
agent -> memory. The honest end-to-end system entry point.

  python arc/run.py easy_a            # 9  real single-pixel tasks
  python arc/run.py easy              # 16 real single-pixel tasks
  python arc/run.py agi 50            # first 50 REAL ARC-AGI-1 tasks (mostly fail)

It reports truthfully: the kernel + unified solver handle the single-object
class; on the full ARC-AGI benchmark most tasks are out of scope and score 0.
That is the real baseline, not a curated win.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.env.dataset import list_tasks, load_task, available  # noqa: E402
from arbor.env.environment import ARCEnvironment  # noqa: E402
from arbor.env.memory import Memory  # noqa: E402
from arbor.expr_solver import candidate_grids, PRODUCTIONS  # noqa: E402


def run(dataset: str, limit: int | None = None, attempts: int = 3, quiet: bool = True):
    """Episode loop, ARC-AGI-2 protocol: solve each TEST PAIR one at a time, with
    its OWN 3 submissions (wrong -> next ranked candidate). A task counts as
    solved only if every test pair is solved within its attempts."""
    tasks = [(tid, load_task(p)) for tid, p in list_tasks(dataset, limit)]
    env = ARCEnvironment(tasks, max_attempts=attempts)
    mem = Memory()
    mem.write_procedural_manifest(PRODUCTIONS, [])

    ctx = env.reset()
    while ctx is not None:
        task, ti = ctx["task"], ctx["test_index"]
        try:
            cands = candidate_grids(task, ti, attempts)
        except Exception:
            cands = []
        i = 0
        while True:
            grid = cands[i] if i < len(cands) else None
            reward, ctx, done, info = env.step(grid)
            if reward >= 1.0 or not info["can_retry"]:
                break
            i += 1

    n_tasks = len({tid for tid, _ in tasks})
    solved = env.solved_tasks()
    for tid, _ in tasks:
        mem.write_episode(tid, {"task_id": tid, "task_solved": env.task_solved(tid)})
    if not quiet:
        for tid, _ in tasks:
            print(f"  {tid:12} {'SOLVED' if env.task_solved(tid) else 'miss'}")
    return {"dataset": dataset, "n": n_tasks, "solved": solved,
            "episodes": mem.episode_count()}


def main():
    if len(sys.argv) < 2:
        print("datasets available:", available())
        print("usage: python arc/run.py <dataset> [limit]")
        return
    dataset = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    r = run(dataset, limit, quiet=False)
    print("-" * 60)
    print(f"dataset={r['dataset']}  solved {r['solved']}/{r['n']}  "
          f"(episodes written: {r['episodes']})")


if __name__ == "__main__":
    main()
