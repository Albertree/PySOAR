"""
solver -- ONE unified ARC agent. A single operator pool + a single base
production-rule set; the decision cycle picks which operators fire per task from
the PROBLEM STATE (not a hardcoded phase pipeline, and not a human choosing which
script to run).

This replaces the two separate solvers (soar_solver = single-object transform,
select_solver = multi-object selection). The base rules branch on facts the
operators write about the task:

  observe   always           -> writes ^multi/^single, the objects
  select    if ^multi        -> discovers the target's selection criterion
  compare   if ^target-known -> in-target vs out-target; writes ^needs-transform
                               or ^transform-none
  generalize if ^needs-transform -> anti-unify the transform schema
  compose   if target-known AND (transform-none OR schema-ready)
  submit    if answer-ready

Emergent per task (same rules):
  single + transform   : observe -> compare -> generalize -> compose -> submit
  multi  + select only : observe -> select  -> compare -> compose -> submit
  multi  + transform   : observe -> select  -> compare -> generalize -> compose -> submit

The branch (does `select` fire? does `generalize` fire?) is decided by the cycle
from WM, which is the point: knowledge-driven operator proposal, not a fixed
sequence.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production  # noqa: E402
from arc.select_solver import fg_objects, find_criterion, apply_criterion  # noqa: E402
from arc.soar_solver import _diag_predict  # noqa: E402


def _lone_output(out_objs):
    return out_objs[0] if len(out_objs) == 1 else None


def _target_in(in_objs, out_obj):
    """The input object that becomes the output object -- matched by color
    (works even when it was moved), falling back to exact cells."""
    by_color = [o for o in in_objs if o["color"] == out_obj["color"]]
    if len(by_color) == 1:
        return by_color[0]
    by_cells = [o for o in in_objs if o["cells"] == out_obj["cells"]]
    return by_cells[0] if len(by_cells) == 1 else None


def _xy(obj):
    """A single object's position = its top-left cell (single-cell -> the cell)."""
    return min(obj["cells"])


def _find_transform(samples):
    """samples: list of (in_obj, out_obj, H, W). Returns position+color rules or
    'none' if the target is unchanged."""
    if all(s[0]["cells"] == s[1]["cells"] and s[0]["color"] == s[1]["color"]
           for s in samples):
        return None  # transform-none (pure selection)
    # color
    if all(s[0]["color"] == s[1]["color"] for s in samples):
        color = ("copy", None)
    elif len({s[1]["color"] for s in samples}) == 1:
        color = ("const", samples[0][1]["color"])
    else:
        color = ("fail", None)
    # position (single-cell targets)
    outs = {_xy(s[1]) for s in samples}
    deltas = {(_xy(s[1])[0] - _xy(s[0])[0], _xy(s[1])[1] - _xy(s[0])[1]) for s in samples}
    if len(outs) == 1:
        pos = ("const", next(iter(outs)))
    elif len(deltas) == 1:
        pos = ("delta", next(iter(deltas)))
    elif all(_diag_predict(*_xy(s[0]), s[2], s[3]) == _xy(s[1]) for s in samples):
        pos = ("diag", None)
    else:
        pos = ("fail", None)
    return {"position": pos, "color": color}


# -- operator bodies ---------------------------------------------------------
def _op_observe(agent):
    task = agent.task
    kg = agent.kg
    kg["pairs"] = []
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        outs = fg_objects(p["output"], f"P{i}.G1")
        out_obj = _lone_output(outs)
        kg["pairs"].append({"in": ins, "out_obj": out_obj,
                            "dims": (len(p["output"]), len(p["output"][0]))})
    tp = task["test"][0]
    kg["test_objs"] = fg_objects(tp["input"], "PT.G0")
    kg["test_dims"] = (len(tp["output"]), len(tp["output"][0]))
    multi = max(len(pr["in"]) for pr in kg["pairs"]) >= 2
    agent.wm.add("S1", "observed", "yes")
    agent.wm.add("S1", "multi" if multi else "single", "yes")
    if not multi:
        # single object: the target is the lone object (no selection needed)
        for pr in kg["pairs"]:
            pr["target_in"] = pr["in"][0]
        kg["criterion"] = {"basis": "only", "detail": "the only object"}
        agent.wm.add("S1", "target-known", "yes")


def _op_select(agent):
    kg = agent.kg
    pairs = []
    for pr in kg["pairs"]:
        tin = _target_in(pr["in"], pr["out_obj"])
        pr["target_in"] = tin
        pairs.append({"sel": tin, "others": [o for o in pr["in"] if o is not tin]})
    crit = find_criterion(pairs)
    kg["criterion"] = crit
    agent.wm.add("S1", "target-known", "yes")
    agent.wm.add("S1", "select-basis", crit["basis"] if crit else "none")
    if crit:
        agent.wm.add("S1", "select-pred", crit["detail"])


def _op_compare(agent):
    kg = agent.kg
    samples = [(pr["target_in"], pr["out_obj"], *pr["dims"]) for pr in kg["pairs"]]
    transform = _find_transform(samples)
    kg["transform"] = transform
    agent.wm.add("S1", "compared", "yes")
    if transform is None:
        agent.wm.add("S1", "transform-none", "yes")
    else:
        agent.wm.add("S1", "needs-transform", "yes")
        agent.wm.add("S1", "coord", "DIFF")


def _op_generalize(agent):
    t = agent.kg["transform"]
    agent.kg["schema"] = t
    agent.wm.add("S1", "schema-ready", "yes")
    agent.wm.add("S1", "rule-position", t["position"][0])
    agent.wm.add("S1", "rule-color", t["color"][0])


def _op_compose(agent):
    kg = agent.kg
    obj = apply_criterion(kg["criterion"], kg["test_objs"]) \
        if kg["criterion"].get("basis") != "only" else kg["test_objs"][0]
    H, W = kg["test_dims"]
    grid = [[0] * W for _ in range(H)]
    schema = kg.get("schema")
    if schema is None:                       # transform-none: keep target as-is
        if obj is not None:
            for (r, c) in obj["cells"]:
                grid[r][c] = obj["color"]
    else:                                    # apply the learned transform
        ir, ic = _xy(obj)
        pk, pv = schema["position"]
        if pk == "const":
            r, c = pv
        elif pk == "delta":
            r, c = ir + pv[0], ic + pv[1]
        elif pk == "diag":
            r, c = _diag_predict(ir, ic, H, W)
        else:
            r, c = ir, ic
        ck, cv = schema["color"]
        color = obj["color"] if ck == "copy" else cv
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = color
    kg["answer"] = grid
    agent.wm.add("S1", "answer-ready", "yes")


def _op_submit(agent):
    agent.wm.add("S1", "done", "yes")


OPERATOR_BODIES = {
    "observe": _op_observe, "select": _op_select, "compare": _op_compare,
    "generalize": _op_generalize, "compose": _op_compose, "submit": _op_submit,
}

# THE BASE PRODUCTION RULES -- procedural knowledge: which operator to propose
# given the PROBLEM STATE. One set for all task kinds; the cycle branches.
PRODUCTIONS = [
    Production("propose-observe",
               [Cond("S1", "task", "loaded"), Cond("S1", "observed", "<x>", negated=True)],
               [Action("S1", "operator", "observe", "+")]),
    # select only when there are multiple objects and no target yet
    Production("propose-select",
               [Cond("S1", "multi", "yes"), Cond("S1", "target-known", "<x>", negated=True)],
               [Action("S1", "operator", "select", "+")]),
    # compare once the target is known, to find any transform
    Production("propose-compare",
               [Cond("S1", "target-known", "yes"), Cond("S1", "compared", "<x>", negated=True)],
               [Action("S1", "operator", "compare", "+")]),
    # generalize only if a transform is needed
    Production("propose-generalize",
               [Cond("S1", "needs-transform", "yes"), Cond("S1", "schema-ready", "<x>", negated=True)],
               [Action("S1", "operator", "generalize", "+")]),
    # compose: two ways in -- no transform, or transform generalized
    Production("propose-compose-noxf",
               [Cond("S1", "transform-none", "yes"), Cond("S1", "answer-ready", "<x>", negated=True)],
               [Action("S1", "operator", "compose", "+")]),
    Production("propose-compose-xf",
               [Cond("S1", "schema-ready", "yes"), Cond("S1", "answer-ready", "<x>", negated=True)],
               [Action("S1", "operator", "compose", "+")]),
    Production("propose-submit",
               [Cond("S1", "answer-ready", "yes"), Cond("S1", "done", "<x>", negated=True)],
               [Action("S1", "operator", "submit", "+")]),
]


def solve(task, record=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record)
    ag.task = task
    ag.kg = {}
    ag.wm.add("S1", "task", "loaded")
    ops = []
    for _ in range(12):
        res = ag.step()
        for d in res.decisions:
            if d[0] == "select":
                ops.append(d[2])
        if ag.wm.contains("S1", "done", "yes"):
            break
    return {"ops": ops, "criterion": ag.kg.get("criterion"),
            "transform": ag.kg.get("transform"),
            "answer": ag.kg.get("answer"),
            "correct": ag.kg.get("answer") == task["test"][0]["output"],
            "trace": ag.trace if record else None}


def predict(task, record=False):
    """Produce an answer grid for EVERY test pair (real ARC tasks have 1+).
    Returns (answers, detail). Out-of-scope tasks yield None answers (the agent
    declines), which the environment scores as wrong -- the honest outcome."""
    answers, detail = [], None
    for tp in task["test"]:
        sub = {"train": task["train"], "test": [tp]}
        try:
            r = solve(sub, record=record)
            answers.append(r.get("answer"))
            detail = r
        except Exception:
            answers.append(None)
    return answers, detail


def main():
    import glob
    easy = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
    multi = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "multi")
    files = sorted(glob.glob(os.path.join(easy, "*.json"))) + sorted(glob.glob(os.path.join(multi, "*.json")))
    solved = 0
    print(f"{'task':16} {'operator sequence (emergent)':48} result")
    print("-" * 78)
    for f in files:
        task = json.load(open(f))
        name = os.path.basename(f).replace(".json", "")
        r = solve(task)
        solved += 1 if r["correct"] else 0
        print(f"{name:16} {' '.join(r['ops']):48} {'SOLVED' if r['correct'] else 'x'}")
    print("-" * 78)
    print(f"solved {solved}/{len(files)}  (ONE agent, one rule set)")


if __name__ == "__main__":
    main()
