# -*- coding: utf-8 -*-
"""
focus_solver -- SLICE 1 of the goal-backward / focus-descent rebuild.

Replaces the hard-coded pipeline (observe->compare->generalize->compose) with the
agreed REFLEX LOOP, applied per node and driven by need/impasse:

solve is an UNDEFINED operator: the agent is given "solve the task" as a GOAL but has
NO knowledge of how. Proposing + selecting solve with no apply rule => OPERATOR
no-change impasse (the canonical SOAR "operator-implementation" subgoal). The substate
that opens exists to FIGURE OUT how to apply solve; focus descends one ARCKG level and
observe/compare gather what implementing it needs:

    S1  ^goal solve, ^focus TASK       -> OBSERVE task first (reveals its pairs P0,P1,Pa)
                                         -> then solve (focus now ^seen) -> ONC -> S2
    S2  ^focus P0                      -> observe P0 + COMPARE peers P0,P1,Pa:
                                             P0,P1 = {input:y, output:y} ; Pa = {input:y, output:n}
                                         -> IMBALANCE discovered HERE: Pa lacks 'output'
                                         -> ^goal DISCOVERED (S2 ^goal G)(G ^node Pa)(G ^produce output)
                                         -> solve (goal + focus seen) -> ONC -> S3
    S3  ^focus P0.G0 ...               -> observe + compare grids -> ^goal -> solve -> ONC -> S4
    ...

Perception->Deliberation->Action: observe (focus-gated) ALWAYS runs before solve
(solve is gated on the focus being ^seen). The GOAL (produce Pa.output) is NOT handed
down -- it is DISCOVERED inside S2 after observing and comparing all peers. solve keys
on ^goal (+ observed focus), so it never encodes "solve by comparing".

Scope (honest): no chunking / result-return is wired yet, so solve never actually
implements -- every level ONC-descends to the bottom, easy000a stays UNSOLVED. What is
verified is the principled control structure (undefined solve -> operator no-change ->
implement-subgoal -> descend, goal discovered in-substate). Wiring result + chunking so
solve produces the grid and is LEARNED is the next slice.

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
    all equal -> COMM, otherwise -> DIFF. Whatever DIFFERS is un-resolved -> compare
    DISCOVERS a GOAL on THIS substate. This discovered ^goal is the ONLY thing that makes
    solve fire here (solve keys on ^goal, never on 'compared', so it carries NO bias
    about HOW to solve). When one sibling lacks a role the others have -- an IMBALANCE
    (e.g. P0,P1 have 'output', Pa lacks it) -- the goal NAMES the node + the role to
    PRODUCE (Pa, output); otherwise the goal just points at the differing properties
    (already on (sid ^diff ...)). This is the goal being *discovered in the substate*,
    after observing + comparing all peers -- not handed down."""
    idx, f = ag.kg["idx"], _focus(ag)
    sid = ag.stack[-1].id                                  # results go on the CURRENT (sub)state
    group = [s for s in _siblings(idx, f)]
    props = {m: idx["nodes"][m].to_json() for m in group}
    keys = sorted(set.intersection(*[set(p.keys()) for p in props.values()]))
    comm, diff, imbal = [], [], None
    for k in keys:
        vals = [props[m][k] for m in group]
        if all(v == vals[0] for v in vals):
            comm.append(k)
            ag.wm.add(sid, "comm", k)
        else:
            diff.append(k)
            ag.wm.add(sid, "diff", k)
            if imbal is None and isinstance(vals[0], dict):     # presence-dict -> imbalance?
                imbal = _imbalance_goal(group, props, k)
    if diff:                                                    # something un-resolved -> a goal
        gid = f"{sid}.goal"
        ag.wm.add(sid, "goal", gid)                             # DISCOVERED goal (fires solve)
        if imbal:
            ag.kg["goal"] = imbal
            ag.wm.add(gid, "node", imbal["minority"])           # e.g. Pa
            ag.wm.add(gid, "produce", imbal["missing"])         # e.g. output (reuses the domain role)
    ag.kg.setdefault("compares", []).append({"node": f, "comm": comm, "diff": diff, "goal": imbal})


# solve has NO body: it is an UNDEFINED operator. There is no apply rule and no
# RHS-function, so selecting it changes nothing => OPERATOR no-change impasse. The
# substate that opens exists to IMPLEMENT solve (SOAR operator-implementation
# subgoaling); focus descends one ARCKG level so it can gather what implementing the
# operator needs. When a future slice produces the result (the output grid), that
# result resolves the impasse and CHUNKING compiles it into solve's apply rule --
# thereafter solve produces the grid directly. observe/compare do the gathering.
OPERATOR_BODIES = {"observe": _op_observe, "compare": _op_compare}


# ---------------------------------------------------------------------------
# productions -- FOCUS-SCOPED conditions (not a global flag pipeline). Each operator
# fires because of the gap at the CURRENT focus, and the order emerges from it.
# ---------------------------------------------------------------------------
# STATE-RELATIVE: <s> binds to the current (sub)state (the one holding ^focus). So the
# SAME rules fire in the top state and in every substate as attention descends -- a
# substate's focus (one level deeper) gets observed/compared by these same productions.
def _propose(name, conds):
    return _propose_named(f"propose*{name}", name, conds)


def _propose_named(prod_name, op_name, conds):
    # same RHS as _propose, but an explicit production name -- lets one operator
    # (solve) have TWO proposal variants (Soar's role*operator*variant convention).
    return Production(
        prod_name, conds,
        [Action("<s>", "operator", "<o>", "+"),
         Action("<o>", "name", op_name), Action("<o>", "node", "<f>")])


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
    # solve: the state has a GOAL and its focus has been OBSERVED -> propose to solve.
    # solve is UNDEFINED -- NO apply rule, NO body (see OPERATOR_BODIES) -- so selecting it
    # changes nothing => operator no-change impasse => a substate to IMPLEMENT it
    # (fine_trace). The ^seen condition is Perception->Deliberation->Action ("observe the
    # focus before you attempt to solve it"), a universal ordering -- NOT a domain method
    # (contrast the deleted solve*post-compare, which wrongly said "solve VIA compare").
    # The order emerges: at S1 observe(task) fires first (task unseen), then solve; in a
    # substate observe->compare run first and compare DISCOVERS the ^goal, then solve.
    Production("propose*solve",
               [Cond("<s>", "goal", "<g>"), Cond("<s>", "focus", "<f>"), Cond("<f>", "seen", "yes")],
               [Action("<s>", "operator", "<o>", "+"), Action("<o>", "name", "solve")]),
    _apply("observe", "seen"),
    _apply("compare", "compared"),
    # NO apply*solve: solve is deliberately un-implemented (that is what makes it impasse).
]


# ---------------------------------------------------------------------------
# input + agent setup (mirrors expr_solver.setup_arc_agent shape so the tracer reuses it)
# ---------------------------------------------------------------------------
def inject_focus(ag):
    """INPUT: separate PERCEPTION from the agent's parsed MODEL (option a).

      input-link (percept):  I2 -^task-> <percept> -^raw-> {json}   [environment-owned, READ-ONLY]
      state (ARCKG model):   S1 -^arckg-> <root> -^example-> P0 ..  [observe/compare fill this]
      top goal:              S1 -^goal-> solve                      [drives solve; NO ^focus at top]
      attention:             S2 -^focus-> P0 ...                    [^focus lives on substates, descends]

    The environment delivers ONLY the raw, unparsed task onto ^io.input-link -- a
    PERCEPT node (its own id) carrying identity (^type/^name) + the literal ^raw dict.
    Perception is environment-owned and never mutated by the agent's operators.

    The parsed ARCKG is the agent's OWN structure, anchored on the top STATE via
    (S1 ^arckg <root>) -- NOT dangling off the input-link. observe/compare augment
    <root> and its descendants (the model), so a substate whose ^focus points one
    ARCKG level deeper is reading/extending the SUPERSTATE's shared, S1-anchored
    model (the SOAR 'substate reads superstate' regime) -- never the raw percept.

    <percept> and <root> are DISTINCT ids on purpose: if they were the same node,
    observe augmenting the model would still be mutating the input-link's percept.
    Justification for the two new symbols (per the no-free-symbols rule):
      ^arckg  -- anchors the agent-built model on its state, so the parse is a
                 deliberative structure, not part of environment perception.
      percept -- keeps perception a separate, immutable node the operators only read."""
    if ag.kg.get("arckg_root") is not None:
        return
    root = build_arckg(ag.task_id, ag.task)
    ag.kg["arckg_root"] = root
    ag.kg["idx"] = index_arckg(root)
    rid = root.node_id
    # (1) raw perception on the input-link -- a PERCEPT node distinct from the ARCKG
    #     root, so augmenting the model never touches what the environment delivered.
    pid = f"percept-{rid}"
    ag.add_input_wme("I2", "task", pid)              # input-link -> percept node
    ag.add_input_wme(pid, "type", "task")            # identity only
    ag.add_input_wme(pid, "name", ag.task_id)
    ag.add_input_wme(pid, "raw", json.dumps(ag.task))  # the literal task dict
    # (2) the parsed ARCKG root on the STATE + the top GOAL + the attention ^focus on the
    #     task. Perception-Deliberation-Action: observe (focus-gated) fires FIRST and
    #     reveals the task's children (the pairs); ONLY THEN does solve fire (it is gated
    #     on the focus being ^seen -- "look before you attempt", a universal ordering, NOT
    #     a domain method). solve, being UNIMPLEMENTED, then yields an operator no-change
    #     impasse and the substate descends one ARCKG level.
    ag.wm.add("S1", "arckg", rid)                     # ARCKG root lives on the state
    ag.wm.add("S1", "goal", "solve")                  # TOP GOAL: solve the task (bootstrap, under-specified)
    ag.wm.add("S1", "focus", rid)                     # attention starts on the task (observe reveals its pairs)


def setup_focus_agent(task, tid="0a", record=False):
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record, io=True)
    ag.task = task
    ag.task_id = tid
    ag.kg = {}
    ag.input_functions.append(inject_focus)
    return ag


OP_DOCS = {
    "observe": "focus 노드의 property + 자식 존재 확인 (자식 내용 X) → ^seen",
    "compare": "focus의 형제들과 property 비교 → COMM/DIFF. 불균형(한 형제가 어떤 role 결여)이면 그 substate에 ^goal 발견(node/produce)",
    "solve": "미구현 operator (apply 규칙·body 없음). ^goal이 있으면 제안되고, 적용 지식이 없어 변화 없음 → operator no-change impasse → 하강(구현 subgoal). 결과가 나오면 chunking으로 학습",
}


# ---------------------------------------------------------------------------
# dashboard generation (reuses dashboard._HTML; separate file, zero impact on the
# working expr_solver dashboard)
# ---------------------------------------------------------------------------
def _dash_data(task, tid="0a", max_cycles=18):   # observe+compare+solve+descend × 4 levels
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
