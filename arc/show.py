"""
inspect -- a PySOAR "debugger" view for the ARC solver: watch WM change through
the decision cycle, see the proposed operators, the preference verdicts, the
selected operator, and (if learning) the learned chunk.

PySOAR has no GUI debugger (that is the C++ Soar's SoarJavaDebugger). This is the
text equivalent for the Python kernel, so you can verify the SOAR flow yourself.

Usage:
  python arc/inspect.py [task.json]      # default: easy000a
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production  # noqa: E402
from pysoar.decide import run_preference_semantics  # noqa: E402
from arc.grid import dims, foreground_pixel, with_pixel  # noqa: E402
from arc.solve import candidate_hypotheses, is_consistent, complexity  # noqa: E402


def _print_wm(wm, label):
    print(f"  WM [{label}]:")
    for (i, a, v) in wm.all():
        print(f"      ({i} ^{a} {v})")


def inspect_task(task: dict) -> None:
    train, test = task["train"], task["test"]
    hyps = candidate_hypotheses(train)
    consistent = [n for n, h in hyps.items() if is_consistent(h, train)]
    inconsistent = [n for n in hyps if n not in consistent]
    simplest = min(consistent, key=complexity) if consistent else None

    print("=" * 64)
    print("1) HYPOTHESES derived from train pair 0 (the 'operators'):")
    for n in hyps:
        tag = ("consistent+BEST" if n == simplest else
               "consistent" if n in consistent else "inconsistent->reject")
        print(f"     {n:14} -> {tag}")

    # build the same productions the solver uses
    prods = []
    for h in consistent:
        acts = [Action("S1", "operator", h, "+")]
        if h == simplest:
            acts.append(Action("S1", "operator", h, ">"))
        prods.append(Production(f"propose-{h}", [Cond("S1", "superstate", "nil")], acts))
    for h in inconsistent:
        prods.append(Production(f"propose-{h}", [Cond("S1", "superstate", "nil")],
                                [Action("S1", "operator", h, "+"), Action("S1", "operator", h, "-")]))

    ag = Agent(prods)
    print("\n2) DECISION CYCLE (watch WM):")
    _print_wm(ag.wm, "initial")
    ag.elaborator.settle(ag.wm)        # PROPOSE phase
    _print_wm(ag.wm, "after PROPOSE settle")

    slot = ag.collect_operator_prefs("S1")
    print("  Operator preferences collected on S1:")
    for ptype, plist in slot.preferences.items():
        for p in plist:
            print(f"      {p!r}  [{ptype.name}]")
    imp, cands = run_preference_semantics(slot)
    print(f"  run_preference_semantics -> impasse={imp.name}, candidates={cands}")

    ag2 = Agent(prods)
    ag2.step()                          # full DECIDE
    sel = ag2.stack[0].selected
    _print_wm(ag2.wm, "after DECIDE (operator installed)")
    print(f"\n3) SELECTED OPERATOR: {sel}")

    # apply selected hypothesis to the test input
    h = hyps[sel]
    tp = test[0]
    fg = foreground_pixel(tp["input"])
    H, W = dims(tp["input"])
    oh, ow = dims(tp["output"])
    pred = with_pixel(oh, ow, *h(*fg, H, W))
    print(f"4) APPLY to test input {fg} -> predicted pixel {foreground_pixel(pred)}")
    print(f"   correct? {pred == tp['output']}  (expected {foreground_pixel(tp['output'])})")
    print("=" * 64)


if __name__ == "__main__":
    default = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a/easy000a.json")
    inspect_task(json.load(open(sys.argv[1] if len(sys.argv) > 1 else default)))
