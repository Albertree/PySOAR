"""
solve -- a single-pixel ARC solver whose hypothesis SELECTION is driven by the
PySOAR decision cycle (M1 preference semantics).

The SOAR-faithful loop (wiki: "training pair = scoring oracle -> preference"):
  1. From train pair 0, derive candidate transformation hypotheses
     (position rule x color rule).
  2. Verify each hypothesis against ALL train pairs (training as oracle).
  3. Express the verdicts as operator preferences and let PySOAR's decision
     cycle SELECT the winning hypothesis:
        consistent   -> acceptable + indifferent   (any consistent one is fine)
        inconsistent -> acceptable + reject
     run_preference_semantics then yields a single winner (or a tie among
     equally-consistent hypotheses, broken deterministically).
  4. Apply the selected hypothesis to the test input -> predicted grid.

Grid arithmetic is Python (see grid.py); PySOAR does the deliberation.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Callable

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Action, Agent, Cond, Production  # noqa: E402
from arc.grid import dims, foreground_pixel, with_pixel  # noqa: E402

# A hypothesis predicts (out_r, out_c, out_color) from (in_r,in_c,in_color,H,W).
Hypothesis = Callable[[int, int, int, int, int], tuple]


# -- position rules ----------------------------------------------------------
def pos_const(R: int, C: int):
    return lambda ir, ic, H, W: (R, C)


def pos_delta(dr: int, dc: int):
    return lambda ir, ic, H, W: (ir + dr, ic + dc)


def pos_diag(ir: int, ic: int, H: int, W: int):
    """Move diagonally down-right until the bottom row; clip column to width."""
    r, c = ir, ic
    while r < H - 1:
        r += 1
        c += 1
    return (r, min(c, W - 1))


# -- color rules -------------------------------------------------------------
def col_const(K: int):
    return lambda icolor: K


def col_copy(icolor: int):
    return icolor


def candidate_hypotheses(train: list) -> dict[str, Hypothesis]:
    """Derive (name -> hypothesis) from train pair 0. Each combines a position
    rule and a color rule; parameters come from the first example (induction),
    to be verified against the rest (oracle)."""
    (ir, ic, icol) = foreground_pixel(train[0]["input"])
    (orr, occ, ocol) = foreground_pixel(train[0]["output"])

    pos_rules = {
        "const": pos_const(orr, occ),
        "delta": pos_delta(orr - ir, occ - ic),
        "diag": pos_diag,
    }
    col_rules = {
        "constC": col_const(ocol),
        "copy": col_copy,
    }

    hyps: dict[str, Hypothesis] = {}
    for pn, pr in pos_rules.items():
        for cn, cr in col_rules.items():
            def make(pr=pr, cr=cr):
                def h(ir, ic, icol, H, W):
                    r, c = pr(ir, ic, H, W)
                    return (r, c, cr(icol))
                return h
            hyps[f"{pn}_{cn}"] = make()
    return hyps


def is_consistent(h: Hypothesis, train: list) -> bool:
    """Does the hypothesis reproduce every train pair's output? (oracle)"""
    for p in train:
        fg = foreground_pixel(p["input"])
        if fg is None:
            return False
        ir, ic, icol = fg
        H, W = dims(p["input"])
        pr, pc, pcol = h(ir, ic, icol, H, W)
        oh, ow = dims(p["output"])
        if with_pixel(oh, ow, pr, pc, pcol) != p["output"]:
            return False
    return True


# simplicity (Occam / initial bias): prefer the least complex rule when several
# fit the training pairs. const position < delta < diagonal-gravity.
_POS_RANK = {"const": 0, "delta": 1, "diag": 2}
_COL_RANK = {"copy": 0, "constC": 1}


def complexity(name: str) -> int:
    pn, cn = name.split("_")
    return _POS_RANK[pn] * 10 + _COL_RANK[cn]


def select_hypothesis(consistent: list[str], inconsistent: list[str]) -> str | None:
    """Let the PySOAR decision cycle pick the winning hypothesis from operator
    preferences. Among train-consistent hypotheses, the simplest (Occam) gets a
    ``best`` preference; inconsistent ones are rejected. run_preference_semantics
    then yields the single winner. Returns the selected hypothesis name."""
    if not consistent:
        return None
    simplest = min(consistent, key=complexity)
    prods = []
    for h in consistent:
        acts = [Action("S1", "operator", h, "+")]
        if h == simplest:
            acts.append(Action("S1", "operator", h, ">"))   # best (simplicity bias)
        prods.append(Production(f"propose-{h}", [Cond("S1", "superstate", "nil")], acts))
    for h in inconsistent:
        prods.append(Production(
            f"propose-{h}", [Cond("S1", "superstate", "nil")],
            [Action("S1", "operator", h, "+"), Action("S1", "operator", h, "-")]))
    ag = Agent(prods)
    ag.step()
    return ag.stack[0].selected


def in_scope(task: dict) -> bool:
    """This solver only handles single-foreground-pixel tasks. Be honest about
    its scope instead of crashing on anything else."""
    for p in task["train"] + task["test"]:
        if foreground_pixel(p["input"]) is None or foreground_pixel(p["output"]) is None:
            return False
    return True


def solve_task(task: dict) -> dict:
    """Solve one ARC task. Returns a result dict."""
    if not in_scope(task):
        return {"consistent": [], "chosen": None, "correct": False,
                "reason": "out-of-scope: not a single-foreground-pixel task"}
    train, test = task["train"], task["test"]
    hyps = candidate_hypotheses(train)

    consistent, inconsistent = [], []
    for name, h in hyps.items():
        (consistent if is_consistent(h, train) else inconsistent).append(name)

    chosen = select_hypothesis(consistent, inconsistent)

    predicted, correct = None, None
    if chosen is not None:
        h = hyps[chosen]
        tp = test[0]
        fg = foreground_pixel(tp["input"])
        H, W = dims(tp["input"])
        oh, ow = dims(tp["output"])
        pr, pc, pcol = h(*fg, H, W)
        predicted = with_pixel(oh, ow, pr, pc, pcol)
        correct = predicted == tp["output"]

    return {
        "consistent": consistent,
        "chosen": chosen,
        "correct": correct,
    }


def main(data_dir: str) -> None:
    import glob
    files = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    solved = 0
    print(f"{'task':12} {'chosen hypothesis':20} {'#consistent':>11}  result")
    print("-" * 60)
    for f in files:
        task = json.load(open(f))
        name = os.path.basename(f).replace(".json", "")
        r = solve_task(task)
        ok = "SOLVED" if r["correct"] else "x"
        solved += 1 if r["correct"] else 0
        print(f"{name:12} {str(r['chosen']):20} {len(r['consistent']):>11}  {ok}")
    print("-" * 60)
    print(f"solved {solved}/{len(files)}")


if __name__ == "__main__":
    default = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
