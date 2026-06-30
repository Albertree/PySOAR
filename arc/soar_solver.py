"""
soar_solver -- a WM-driven ARC solver built from GENERAL operators over ARCKG,
driven by the PySOAR decision cycle.

This is the redesign the wiki (arbor-operators.md) calls for: operators are
functional and general (observe / compare / generalize / compose / submit), NOT
task-specific hypotheses. The task knowledge lives in ARCKG node properties and
in the *schema* that `generalize` (anti-unification) produces -- not in a
hand-coded hypothesis list. The same operators handle any single-object property
transform; coverage grows by adding ARCKG properties, not operators.

Architecture:
  - ARCKG (real, from ~/Desktop/ARC-solver) supplies node properties + compare.
  - Each operator is a Python *body* (the SOAR external-application pattern) that
    reads/writes WM; PySOAR's decision cycle proposes/selects them by
    precondition + preference, so every step is an operator mutating WM.
  - Watch the flow:  observe -> compare -> generalize -> compose -> submit, with
    WM gaining (S1 ^observed yes) -> (^compared yes) -> (^schema-ready yes) -> ...

Run:  python arc/soar_solver.py            # solves data/ARC_easy_a, WM-driven
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ARC_SOLVER = os.path.expanduser("~/Desktop/ARC-solver")
if _ARC_SOLVER not in sys.path:
    sys.path.insert(0, _ARC_SOLVER)

from pysoar import Agent, Cond, Action, Production  # noqa: E402
from ARCKG.grid import Grid                          # noqa: E402  (real ARCKG)
from ARCKG.comparison import compare as kg_compare   # noqa: E402


# -- ARCKG helpers -----------------------------------------------------------
def _foreground_object(raw, node_id):
    """The single non-background ARCKG object of a grid (single-pixel class)."""
    g = Grid(node_id, raw)
    g.extract_objects()
    for o in g.objects:
        j = o.to_json()
        color = next((k for k, v in j["color"].items() if v), 0)
        if color != 0:
            return o, color, tuple(j["coordinate"][0])  # (obj, color, (r,c))
    return None, 0, None


def _dims(raw):
    return len(raw), len(raw[0])


# -- general operators (Python bodies; precondition+preference = productions) -
def _op_observe(agent):
    """observe: load ARCKG objects for every train pair + the test input."""
    task = agent.task
    kg = agent.kg
    kg["train"] = []
    for i, p in enumerate(task["train"]):
        io = _foreground_object(p["input"], f"P{i}.G0")
        oo = _foreground_object(p["output"], f"P{i}.G1")
        kg["train"].append((io, oo, _dims(p["output"])))
    tp = task["test"][0]
    kg["test_in"] = _foreground_object(tp["input"], "PT.G0")
    kg["test_dims"] = _dims(tp["output"])
    agent.wm.add("S1", "observed", "yes")
    agent.wm.add("S1", "pairs", len(kg["train"]))


def _op_compare(agent):
    """compare: ARCKG compare in-object vs out-object per train pair; record the
    per-property COMM/DIFF and the raw (in,out) values for generalize."""
    kg = agent.kg
    recs = []
    for (io, oo, _od) in kg["train"]:
        (in_obj, in_col, in_xy) = io
        (out_obj, out_col, out_xy) = oo
        receipt = kg_compare(in_obj, out_obj)          # real ARCKG compare
        cat = (receipt.get("result") or {}).get("category", {})
        recs.append({
            "color": (in_col, out_col, cat.get("color", {}).get("type")),
            "coord": (in_xy, out_xy),
        })
    kg["receipts"] = recs
    # mirror salient verdicts so the cycle (and you) can see them
    color_comm = all(r["color"][0] == r["color"][1] for r in recs)
    agent.wm.add("S1", "compared", "yes")
    agent.wm.add("S1", "color", "COMM" if color_comm else "DIFF")
    agent.wm.add("S1", "coord", "COMM" if all(r["coord"][0] == r["coord"][1] for r in recs) else "DIFF")


def _diag_predict(ir, ic, H, W):
    r, c = ir, ic
    while r < H - 1:
        r += 1
        c += 1
    return (r, min(c, W - 1))


def _op_generalize(agent):
    """generalize (anti-unify): least-general rule per property across pairs."""
    kg = agent.kg
    recs = kg["receipts"]
    # color rule
    if all(r["color"][0] == r["color"][1] for r in recs):
        color_rule = ("copy", None)
    elif len({r["color"][1] for r in recs}) == 1:
        color_rule = ("const", recs[0]["color"][1])
    else:
        color_rule = ("fail", None)
    # position rule
    outs = {r["coord"][1] for r in recs}
    deltas = {(o[0] - i[0], o[1] - i[1]) for (i, o) in (r["coord"] for r in recs)}
    if len(outs) == 1:
        pos_rule = ("const", next(iter(outs)))
    elif len(deltas) == 1:
        pos_rule = ("delta", next(iter(deltas)))
    elif all(_diag_predict(*r["coord"][0], *kg["train"][k][2]) == r["coord"][1]
             for k, r in enumerate(recs)):
        pos_rule = ("diag", None)
    else:
        pos_rule = ("fail", None)
    kg["schema"] = {"color": color_rule, "position": pos_rule}
    agent.wm.add("S1", "schema-ready", "yes")
    # the LEARNED RULE, visible in WM (procedural knowledge)
    agent.wm.add("S1", "rule-color", color_rule[0])
    agent.wm.add("S1", "rule-position", pos_rule[0])


def _op_compose(agent):
    """compose: apply the schema to the test input object -> answer grid."""
    kg = agent.kg
    (in_obj, in_col, (ir, ic)) = kg["test_in"]
    H, W = kg["test_dims"]
    pos_kind, pos_val = kg["schema"]["position"]
    if pos_kind == "const":
        r, c = pos_val
    elif pos_kind == "delta":
        r, c = ir + pos_val[0], ic + pos_val[1]
    elif pos_kind == "diag":
        r, c = _diag_predict(ir, ic, H, W)
    else:
        r, c = ir, ic
    col_kind, col_val = kg["schema"]["color"]
    color = in_col if col_kind == "copy" else col_val
    grid = [[0] * W for _ in range(H)]
    if 0 <= r < H and 0 <= c < W:
        grid[r][c] = color
    kg["answer"] = grid
    agent.wm.add("S1", "answer-ready", "yes")


def _op_submit(agent):
    agent.wm.add("S1", "done", "yes")


OPERATOR_BODIES = {
    "observe": _op_observe,
    "compare": _op_compare,
    "generalize": _op_generalize,
    "compose": _op_compose,
    "submit": _op_submit,
}

# proposal productions: precondition (testable WM) -> propose general operator.
# Preconditions serialize the operators (each proposable only once the prior's
# effect lands), so there is a single candidate per step -- a clean WM-driven run.
PRODUCTIONS = [
    Production("propose-observe",
               [Cond("S1", "task", "loaded"), Cond("S1", "observed", "<x>", negated=True)],
               [Action("S1", "operator", "observe", "+")]),
    Production("propose-compare",
               [Cond("S1", "observed", "yes"), Cond("S1", "compared", "<x>", negated=True)],
               [Action("S1", "operator", "compare", "+")]),
    Production("propose-generalize",
               [Cond("S1", "compared", "yes"), Cond("S1", "schema-ready", "<x>", negated=True)],
               [Action("S1", "operator", "generalize", "+")]),
    Production("propose-compose",
               [Cond("S1", "schema-ready", "yes"), Cond("S1", "answer-ready", "<x>", negated=True)],
               [Action("S1", "operator", "compose", "+")]),
    Production("propose-submit",
               [Cond("S1", "answer-ready", "yes"), Cond("S1", "done", "<x>", negated=True)],
               [Action("S1", "operator", "submit", "+")]),
]


def solve(task: dict, trace: bool = False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES)
    ag.task = task
    ag.kg = {}
    ag.wm.add("S1", "task", "loaded")
    seq = []
    for _ in range(12):
        before = len(ag.wm)
        res = ag.step()
        for d in res.decisions:
            if d[0] == "select":
                seq.append(d[2])
                if trace:
                    print(f"  op={d[2]:11} -> WM now: "
                          f"{[f'{a}={v}' for (i,a,v) in ag.wm.all() if i=='S1' and a not in ('task','type','superstate','operator')]}")
        if ag.wm.contains("S1", "done", "yes"):
            break
        if len(ag.wm) == before and not res.decisions:
            break
    answer = ag.kg.get("answer")
    correct = answer == task["test"][0]["output"]
    rule = (ag.kg.get("schema") or {})
    return {"ops": seq, "rule": rule, "correct": correct, "answer": answer}


def main(data_dir):
    import glob
    files = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    solved = 0
    print(f"{'task':12} {'operators (WM-driven)':52} {'rule':28} result")
    print("-" * 104)
    for f in files:
        task = json.load(open(f))
        name = os.path.basename(f).replace(".json", "")
        r = solve(task)
        solved += 1 if r["correct"] else 0
        ops = " ".join(r["ops"])
        rule = f"pos={r['rule'].get('position',('?',))[0]},col={r['rule'].get('color',('?',))[0]}"
        print(f"{name:12} {ops:52} {rule:28} {'SOLVED' if r['correct'] else 'x'}")
    print("-" * 104)
    print(f"solved {solved}/{len(files)}")


if __name__ == "__main__":
    default = os.path.expanduser("~/Desktop/ARC-solver/data/ARC_easy_a")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
