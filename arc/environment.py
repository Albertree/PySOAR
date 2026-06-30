"""
environment -- ARC evaluation environment, ARC-AGI-2 protocol.

IMPORTANT (corrected): each TEST PAIR is solved ONE AT A TIME. A test pair gets
up to N=3 submissions (submit → wrong → retry); only then does the next test pair
begin, with a FRESH 3 attempts. You never submit multiple test pairs at once.

A TASK is solved iff every one of its test pairs was solved (each within its own
3 attempts).

  ctx = env.reset()                  # first (task, test-pair)
  while ctx is not None:
      task, ti = ctx["task"], ctx["test_index"]
      grid = agent_answer(task, ti)  # ONE output grid for THIS test pair
      reward, ctx, done, info = env.step(grid)
"""

from __future__ import annotations

DEFAULT_MAX_ATTEMPTS = 3


def grids_equal(a, b) -> bool:
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    return all(len(ra) == len(rb) and ra == rb for ra, rb in zip(a, b))


class ARCEnvironment:
    def __init__(self, tasks: list, max_attempts: int = DEFAULT_MAX_ATTEMPTS):
        """tasks: list of (task_id, task_dict)."""
        self._max = max_attempts
        # one item per test pair, in order
        self._items = []
        for tid, task in tasks:
            for ti in range(len(task["test"])):
                self._items.append({"tid": tid, "task": task, "ti": ti})
        self._i = -1
        self._attempts_left = 0
        self._solved = {}        # tid -> set(test_index solved)
        self._ntests = {tid: len(task["test"]) for tid, task in tasks}
        self.trace = []

    def _ctx(self):
        if self._i < 0 or self._i >= len(self._items):
            return None
        it = self._items[self._i]
        return {"task_id": it["tid"], "task": it["task"], "test_index": it["ti"],
                "attempts_left": self._attempts_left}

    def reset(self):
        self._i = 0
        self._attempts_left = self._max
        self._solved = {}
        self.trace = []
        return self._ctx()

    def _advance(self):
        self._i += 1
        self._attempts_left = self._max
        return self._ctx()

    def step(self, grid):
        """Score ONE output grid against the CURRENT test pair. Returns
        (reward, next_ctx, done, info)."""
        info = {"correct": False, "attempts_left": 0, "can_retry": False}
        if self._i >= len(self._items):
            return 0.0, None, True, info
        it = self._items[self._i]
        gt = it["task"]["test"][it["ti"]]["output"]
        ok = grids_equal(grid, gt)
        reward = 1.0 if ok else 0.0
        self._attempts_left -= 1
        can_retry = (not ok) and (self._attempts_left > 0)
        info.update(correct=ok, attempts_left=self._attempts_left, can_retry=can_retry)
        self.trace.append({"task_id": it["tid"], "test_index": it["ti"],
                           "reward": reward, "attempts_left": self._attempts_left})
        if ok:
            self._solved.setdefault(it["tid"], set()).add(it["ti"])
        if ok or not can_retry:
            nxt = self._advance()
            return reward, nxt, nxt is None, info
        return reward, self._ctx(), False, info        # retry SAME test pair

    def task_solved(self, tid) -> bool:
        return len(self._solved.get(tid, set())) == self._ntests.get(tid, 0)

    def solved_tasks(self) -> int:
        return sum(1 for tid in self._ntests if self.task_solved(tid))
