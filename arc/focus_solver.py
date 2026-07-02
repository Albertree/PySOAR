# -*- coding: utf-8 -*-
"""
focus_solver -- SLICE 1 of the goal-backward / focus-descent rebuild.

Replaces the hard-coded pipeline (observe->compare->generalize->compose) with the
agreed REFLEX LOOP, applied per node and driven by need/impasse:

    visit(focus):
        observe(focus)                 # this node's property + which children exist
        if siblings exist: compare      # same-level property comparison -> COMM/DIFF
        if stuck (can't progress here): DESCEND  # focus -> a child (deeper info)

On easy000a this GENERATES the opening instead of scripting it:
    focus=TASK  -> observe (no siblings) -> stuck -> DESCEND
    focus=PAIR  -> observe + COMPARE roles across pairs:
                       P0,P1 = {input:y, output:y} ; Pa = {input:y, output:n}
                   -> IMBALANCE: Pa is missing 'output'
                   -> DERIVE goal  (S1 ^goal G)(G ^complete ..Pa ^missing output)   <- NOT hard-coded
                   -> DESCEND to GRID
    focus=GRID  -> observe + compare grid properties (size COMM, color/contents DIFF) ...

Scope (honest): this slice shows the DESCENT + GOAL-DERIVATION in the dashboard.
Arg resolution / compose / submit (the actual answer build) are the next slice.
descend here is a focus-move operator (model A); upgrading it to a real no-change
impasse -> substate (model B) is also next.

    python3 arc/focus_solver.py        # -> arc/focus_dashboard.html
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production          # noqa: E402
from arc.expr_solver import build_arckg, _load_value         # noqa: E402 (reuse, read-only)


# ---------------------------------------------------------------------------
# ARCKG index: id -> node / parent / children / level (so observe/compare/descend
# can walk the hierarchy the lens defines).
# ---------------------------------------------------------------------------
def index_arckg(root):
    nodes, parent, children, level, edges = {}, {}, {}, {}, {}

    def walk(node, par, lvl):
        nid = node.node_id
        nodes[nid] = node
        parent[nid] = par
        level[nid] = lvl
        # (edge_name, child) -- the SAME edge names the existing ARCKG/expr_solver uses
        kid_edges = []
        if lvl == "task":
            for c in (getattr(node, "example_pairs", []) or []):
                kid_edges.append(("example", c))
            for c in (getattr(node, "test_pairs", []) or []):
                kid_edges.append(("test", c))
            for _, c in kid_edges:
                walk(c, nid, "pair")
        elif lvl == "pair":
            for attr, edge in (("input_grid", "input"), ("output_grid", "output")):
                g = getattr(node, attr, None)
                if g is not None:
                    kid_edges.append((edge, g))
                    walk(g, nid, "grid")
        elif lvl == "grid":
            for o in (getattr(node, "objects", None) or []):
                kid_edges.append(("object", o))
                walk(o, nid, "object")
        children[nid] = [c.node_id for _, c in kid_edges]
        edges[nid] = [(e, c.node_id) for e, c in kid_edges]

    walk(root, None, "task")
    return {"nodes": nodes, "parent": parent, "children": children,
            "level": level, "edges": edges}


def _focus(ag):
    """Focus node of the CURRENT (bottom) goal -- attention descends via substates."""
    sid = ag.stack[-1].id
    return next((v for (i, a, v) in ag.wm if i == sid and a == "focus"), None)


def _siblings(idx, f):
    par = idx["parent"][f]
    return [s for s in idx["children"].get(par, [])] if par else []


# ---------------------------------------------------------------------------
# operator bodies (RHS functions): the ARCKG/comparison work
# ---------------------------------------------------------------------------
def _op_observe(ag):
    """Look at the FOCUS node: load its own properties + which children it has
    (refs only). If it has same-level siblings, load THEIR comparable property too
    (so compare can run). No siblings -> nothing to compare -> ready to descend."""
    idx, f = ag.kg["idx"], _focus(ag)
    node = idx["nodes"][f]
    ag.wm.add(f, "type", idx["level"][f])
    for k, v in node.to_json().items():
        _load_value(ag.wm, f, k, v)
    kids = idx["edges"][f]
    for edge, c in kids:
        ag.wm.add(f, edge, c)                  # child EXISTS (ref, ARCKG edge name); contents not loaded
    sibs = [s for s in _siblings(idx, f) if s != f]
    if sibs:
        ag.wm.add(f, "has-siblings", "yes")
        for s in sibs:                          # load peers' property for the comparison
            ag.wm.add(s, "type", idx["level"][s])
            for k, v in idx["nodes"][s].to_json().items():
                _load_value(ag.wm, s, k, v)
    else:
        ag.wm.add(f, "has-siblings", "no")      # no peers here -> compare cannot fire


def _imbalance_goal(group, props, key):
    """A FLAT presence-dict property (value -> bool), e.g. roles={input:T, output:F},
    where ONE member differs from the majority -> that member is incomplete; return
    what it is missing. Non-flat / non-bool dicts (nested grid props) -> skip (None)."""
    dicts = [props[m][key] for m in group]
    if not all(isinstance(d, dict) and all(isinstance(v, bool) for v in d.values())
               for d in dicts):
        return None
    sigs = {m: tuple(sorted(props[m][key].items())) for m in group}
    cnt = Counter(sigs.values())
    if len(cnt) < 2:
        return None
    majority = dict(cnt.most_common(1)[0][0])
    for m in group:
        if sigs[m] != cnt.most_common(1)[0][0]:
            mind = props[m][key]
            missing = [sk for sk, sv in majority.items() if sv and not mind.get(sk)]
            return {"minority": m, "missing": missing[0] if missing else "?"}
    return None


def _op_compare(ag):
    """Compare the focus node with its same-level siblings, property by property:
    all equal -> COMM, otherwise -> DIFF. A presence-dict DIFF with a single odd-one-out
    is an IMBALANCE -> DERIVE the goal (complete the minority's missing role)."""
    idx, f = ag.kg["idx"], _focus(ag)
    sid = ag.stack[-1].id                                  # results go on the CURRENT (sub)state
    group = [s for s in _siblings(idx, f)]
    props = {m: idx["nodes"][m].to_json() for m in group}
    keys = sorted(set.intersection(*[set(p.keys()) for p in props.values()]))
    comm, diff, goal = [], [], None
    for k in keys:
        vals = [props[m][k] for m in group]
        if all(v == vals[0] for v in vals):
            comm.append(k)
            ag.wm.add(sid, "comm", k)
        else:
            diff.append(k)
            ag.wm.add(sid, "diff", k)
            if isinstance(vals[0], dict):                       # presence-dict -> imbalance?
                g = _imbalance_goal(group, props, k)
                gid = f"{sid}.goal"
                if g and not ag.wm.contains(sid, "refine-goal", gid):
                    goal = g
                    ag.kg["goal"] = g
                    ag.wm.add(sid, "refine-goal", gid)          # goal EVOLVES on this substate
                    ag.wm.add(gid, "complete", g["minority"])
                    ag.wm.add(gid, "missing", g["missing"])
    ag.kg.setdefault("compares", []).append({"node": f, "comm": comm, "diff": diff, "goal": goal})


# descend is NO LONGER an operator. Going deeper is the ARCHITECTURE's response to a
# state no-change impasse (no operator applicable at this focus -> substate, focus
# descends one ARCKG level). See fine_trace run(): the impasse branch opens the substate.
OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare}


# ---------------------------------------------------------------------------
# productions -- FOCUS-SCOPED conditions (not a global flag pipeline). Each operator
# fires because of the gap at the CURRENT focus, and the order emerges from it.
# ---------------------------------------------------------------------------
# STATE-RELATIVE: <s> binds to the current (sub)state (the one holding ^focus). So the
# SAME rules fire in the top state and in every substate as attention descends -- a
# substate's focus (one level deeper) gets observed/compared by these same productions.
def _propose(name, conds):
    return Production(
        f"propose*{name}", conds,
        [Action("<s>", "operator", "<o>", "+"),
         Action("<o>", "name", name), Action("<o>", "node", "<f>")])


def _apply(name, attr):
    # writes the result flag ON THE FOCUS NODE the operator targeted (<o> ^node <f>)
    return Production(
        f"apply*{name}",
        [Cond("<s>", "operator", "<o>"), Cond("<o>", "name", name), Cond("<o>", "node", "<f>")],
        [Action("<f>", attr, "yes")])


PRODUCTIONS = [
    # observe: reflexive -- the current state's focus node is not yet seen
    _propose("observe", [Cond("<s>", "focus", "<f>"), Cond("<f>", "seen", "<x>", negated=True)]),
    # compare: focus seen AND it has same-level siblings, not yet compared
    _propose("compare", [Cond("<s>", "focus", "<f>"), Cond("<f>", "seen", "yes"),
                         Cond("<f>", "has-siblings", "yes"), Cond("<f>", "compared", "<x>", negated=True)]),
    _apply("observe", "seen"),
    _apply("compare", "compared"),
    # NO descend rule: when neither observe nor compare can fire, NO operator is
    # proposable -> state no-change impasse -> the architecture opens a substate and
    # descends one level (fine_trace). "nothing applies" is the verified insufficiency.
]


# ---------------------------------------------------------------------------
# input + agent setup (mirrors expr_solver.setup_arc_agent shape so the tracer reuses it)
# ---------------------------------------------------------------------------
def inject_focus(ag):
    """INPUT: IDENTICAL to expr_solver.inject_task -- the environment delivers the raw
    task onto ^io.input-link (identity ^type/^name + the literal ^raw dict). The ONLY
    thing added on top is the attention pointer (S1 ^focus <task>) so observe/descend
    know where to look. The task node is anchored in the WM tree via the input-link
    (S1 -> io -> input-link -> task), exactly as before -- no invented structural edge.
    observe/descend then build the structured lens lazily from ^raw."""
    if ag.kg.get("arckg_root") is not None:
        return
    root = build_arckg(ag.task_id, ag.task)
    ag.kg["arckg_root"] = root
    ag.kg["idx"] = index_arckg(root)
    nid = root.node_id
    ag.add_input_wme("I2", "task", nid)              # input-link -> Task node (as before)
    ag.add_input_wme(nid, "type", "task")            # identity only
    ag.add_input_wme(nid, "name", ag.task_id)
    ag.add_input_wme(nid, "raw", json.dumps(ag.task))  # the literal task dict
    ag.wm.add("S1", "goal", "solve")                  # TOP GOAL: solve the task (given on arrival)
    ag.wm.add("S1", "focus", nid)                     # attention pointer (descends via substates)


def setup_focus_agent(task, tid="0a", record=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record, io=True)
    ag.task = task
    ag.task_id = tid
    ag.kg = {}
    ag.input_functions.append(inject_focus)
    return ag


OP_DOCS = {
    "observe": "focus 노드의 property + 자식 존재 확인 (자식 내용 X) → ^seen",
    "compare": "focus의 형제들과 property 비교 → COMM/DIFF, 불균형이면 goal 도출",
}


# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------
def _dash_data(task, tid="0a", max_cycles=12):   # enough to descend task->pair->grid->object
    from arc.fine_trace import fine_trace
    events = fine_trace(task, tid, setup=setup_focus_agent, max_cycles=max_cycles)
    wm_states, idx = [], {}
    for e in events:
        key = tuple(tuple(t) for t in e["wm"])
        if key not in idx:
            idx[key] = len(wm_states)
            wm_states.append(e["wm"])
        e["wm_state"] = idx[key]
        del e["wm"]
    return {
        "id": tid, "events": events, "wm_states": wm_states,
        "grids": {"train": task["train"],
                  "test": [{"input": tp["input"]} for tp in task["test"]]},
        "candidates": [], "correct_attempt": None, "n_steps": len(events),
    }


def _rules_manifest():
    return [{"name": p.name,
             "if": [{"id": c.id, "attr": c.attr, "val": c.value, "neg": c.negated} for c in p.conditions],
             "then": [{"id": a.id, "attr": a.attr, "val": a.value, "pref": a.pref} for a in p.actions]}
            for p in PRODUCTIONS]


def make_dashboard(task, tid="0a"):
    from arc.dashboard import _HTML
    data = {"dataset": "focus (slice 1)", "tasks": [_dash_data(task, tid)],
            "rules": _rules_manifest(), "op_docs": OP_DOCS}
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "focus_dashboard.html")
    with open(out, "w") as f:
        f.write(_HTML.replace("__DATA__", json.dumps(data)))
    return out


if __name__ == "__main__":
    from arc.dataset import list_tasks, load_task
    tid, path = list_tasks("easy_a")[0]          # real task id (e.g. easy000a), not a made-up "0a"
    out = make_dashboard(load_task(path), tid)
    print(f"wrote {out}  (task {tid})\nopen it:  open {out}")
