"""
select_solver -- multi-object ARC solving with the general `select` operator,
driven by the PySOAR decision cycle over real ARCKG.

The wiki's `select` operator finds the *target* (which object) by a basis that
it must discover: a fixed attribute value, a generalized attribute (extremum),
or a relation to another object. Here `select` inspects which object survives in
the train outputs and searches for the consistent selection criterion.

Operators (general, WM-driven):  observe -> select -> compose -> submit
  observe  : extract every ARCKG object of each grid
  select   : discover the selection criterion (color= / argmax-area / same-row)
  compose  : apply the criterion to the test input -> keep that object
  submit   : finalize

The SAME `select` operator solves all three task kinds; only the discovered
criterion differs. Coverage grows by adding attributes/relations, not operators.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from soar import Agent, Cond, Action, Production  # noqa: E402
from arbor.perception.arckg.grid import Grid         # noqa: E402  (vendored)


# -- ARCKG object access -----------------------------------------------------
def fg_objects(raw, node_id):
    g = Grid(node_id, raw)
    g.extract_objects()
    objs = []
    for o in g.objects:
        j = o.to_json()
        color = next((k for k, v in j["color"].items() if v), 0)
        if color == 0:
            continue
        cells = frozenset((r, c) for r, c in j["coordinate"])
        objs.append({
            "color": color, "area": j["area"], "cells": cells,
            "rows": frozenset(r for r, c in j["coordinate"]),
            "cols": frozenset(c for r, c in j["coordinate"]),
        })
    return objs


def _selected(in_objs, out_objs):
    """Which input object survived in the output (matched by cell signature)?"""
    sigs = {o["cells"] for o in out_objs}
    sel = [o for o in in_objs if o["cells"] in sigs]
    return sel[0] if len(sel) == 1 else None


# -- selection-criterion finders (the `select` basis search) -----------------
def _try_fixed_color(pairs):
    sel0 = pairs[0]["sel"]
    K = sel0["color"]
    for p in pairs:
        if p["sel"]["color"] != K:
            return None
        if any(o["color"] == K for o in p["others"]):
            return None
    return {"basis": "color", "detail": f"color=={K}", "value": K}


def _try_extremum(pairs, attr):
    for fn, tag in ((max, "argmax"), (min, "argmin")):
        ok = True
        for p in pairs:
            allo = [p["sel"]] + p["others"]
            best = fn(allo, key=lambda o: o[attr])
            if best is not p["sel"] or sum(1 for o in allo if o[attr] == p["sel"][attr]) != 1:
                ok = False
                break
        if ok:
            return {"basis": tag, "detail": f"{tag}({attr})", "attr": attr, "kind": tag}
    return None


def _try_relation(pairs):
    # same-row / same-col with a fixed-color marker the selected object relates to
    for rel, key in (("same_row", "rows"), ("same_col", "cols")):
        # candidate marker colors = colors present (as 'others') in every pair
        common = set.intersection(*[{o["color"] for o in p["others"]} for p in pairs]) if pairs else set()
        for M in sorted(common):
            ok = True
            for p in pairs:
                marker = next((o for o in p["others"] if o["color"] == M), None)
                if marker is None:
                    ok = False
                    break
                shares = [o for o in [p["sel"]] + p["others"]
                          if o is not marker and o[key] & marker[key]]
                if shares != [p["sel"]]:
                    ok = False
                    break
            if ok:
                return {"basis": "relation", "detail": f"{rel}(marker color={M})",
                        "rel": rel, "key": key, "marker": M}
    return None


def find_criterion(pairs):
    return (_try_fixed_color(pairs) or _try_extremum(pairs, "area") or _try_relation(pairs))


def apply_criterion(crit, objs):
    """Return the object selected from `objs` by the criterion (or None)."""
    if crit is None:
        return None
    b = crit["basis"]
    if b == "color":
        cands = [o for o in objs if o["color"] == crit["value"]]
        return cands[0] if len(cands) == 1 else None
    if b in ("argmax", "argmin"):
        fn = max if crit["kind"] == "argmax" else min
        return fn(objs, key=lambda o: o[crit["attr"]])
    if b == "relation":
        marker = next((o for o in objs if o["color"] == crit["marker"]), None)
        if marker is None:
            return None
        shares = [o for o in objs if o is not marker and o[crit["key"]] & marker[crit["key"]]]
        return shares[0] if len(shares) == 1 else None
    return None


# -- general operators (bodies) ---------------------------------------------
def _op_observe(agent):
    task = agent.task
    pairs = []
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        outs = fg_objects(p["output"], f"P{i}.G1")
        sel = _selected(ins, outs)
        others = [o for o in ins if o is not sel]
        pairs.append({"in": ins, "out": outs, "sel": sel, "others": others})
    agent.kg["pairs"] = pairs
    tp = task["test"][0]
    agent.kg["test_objs"] = fg_objects(tp["input"], "PT.G0")
    agent.kg["test_dims"] = (len(tp["output"]), len(tp["output"][0]))
    agent.wm.add("S1", "observed", "yes")
    agent.wm.add("S1", "objects", len(agent.kg["pairs"][0]["in"]))


def _op_select(agent):
    crit = find_criterion(agent.kg["pairs"])
    agent.kg["criterion"] = crit
    agent.wm.add("S1", "selected", "yes")
    agent.wm.add("S1", "select-basis", crit["basis"] if crit else "none")
    if crit:
        agent.wm.add("S1", "select-pred", crit["detail"])


def _op_compose(agent):
    crit = agent.kg["criterion"]
    obj = apply_criterion(crit, agent.kg["test_objs"])
    H, W = agent.kg["test_dims"]
    grid = [[0] * W for _ in range(H)]
    if obj is not None:
        for (r, c) in obj["cells"]:
            grid[r][c] = obj["color"]
    agent.kg["answer"] = grid
    agent.wm.add("S1", "answer-ready", "yes")


def _op_submit(agent):
    agent.wm.add("S1", "done", "yes")


OPERATOR_BODIES = {
    "observe": _op_observe, "select": _op_select,
    "compose": _op_compose, "submit": _op_submit,
}

PRODUCTIONS = [
    Production("propose-observe",
               [Cond("S1", "task", "loaded"), Cond("S1", "observed", "<x>", negated=True)],
               [Action("S1", "operator", "observe", "+")]),
    Production("propose-select",
               [Cond("S1", "observed", "yes"), Cond("S1", "selected", "<x>", negated=True)],
               [Action("S1", "operator", "select", "+")]),
    Production("propose-compose",
               [Cond("S1", "selected", "yes"), Cond("S1", "answer-ready", "<x>", negated=True)],
               [Action("S1", "operator", "compose", "+")]),
    Production("propose-submit",
               [Cond("S1", "answer-ready", "yes"), Cond("S1", "done", "<x>", negated=True)],
               [Action("S1", "operator", "submit", "+")]),
]


def solve(task, trace=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES)
    ag.task = task
    ag.kg = {}
    ag.wm.add("S1", "task", "loaded")
    ops = []
    for _ in range(10):
        res = ag.step()
        for d in res.decisions:
            if d[0] == "select":
                ops.append(d[2])
                if trace:
                    facts = [f"{a}={v}" for (i, a, v) in ag.wm.all()
                             if i == "S1" and a not in ("task", "type", "superstate", "operator")]
                    print(f"  op={d[2]:9} -> {facts}")
        if ag.wm.contains("S1", "done", "yes"):
            break
    answer = ag.kg.get("answer")
    return {"ops": ops, "criterion": ag.kg.get("criterion"),
            "correct": answer == task["test"][0]["output"]}


def main(data_dir):
    import glob
    files = sorted(glob.glob(os.path.join(data_dir, "*.json")))
    solved = 0
    print(f"{'task':18} {'operators':38} {'select basis':30} result")
    print("-" * 96)
    for f in files:
        task = json.load(open(f))
        name = os.path.basename(f).replace(".json", "")
        r = solve(task)
        solved += 1 if r["correct"] else 0
        basis = r["criterion"]["detail"] if r["criterion"] else "none"
        print(f"{name:18} {' '.join(r['ops']):38} {basis:30} {'SOLVED' if r['correct'] else 'x'}")
    print("-" * 96)
    print(f"solved {solved}/{len(files)}")


if __name__ == "__main__":
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "multi")
    main(sys.argv[1] if len(sys.argv) > 1 else default)
