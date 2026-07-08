"""
expr_solver -- single-object solving via the ARBOR DSL (make_grid + coloring) with
ARGUMENT EXPRESSIONS, driven by the PySOAR decision cycle.

Replaces the hand-coded position/color "finders" with expression resolution: each
argument (position/color/size/fill) is resolved to the most GENERAL expression
over ARCKG properties consistent across the train pairs (arc/dsl.py). The output
is then built by the two frozen transformations.

  observe   -> the single foreground object per grid
  compare   -> per-pair (input context, output value) for each argument
  generalize-> resolve each argument to a general expression (specific -> general)
  compose   -> make_grid(size, fill) + coloring(position, color)
  submit

Why this beats the hand-coded version: a constant output coordinate (5,5) on a
6x6 grid resolves to corner-br = (H-1, W-1), which generalizes across grid sizes,
instead of the literal (5,5). The expression space is open and reusable.
Scope (honest): single foreground pixel transforms.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pysoar import Agent, Cond, Action, Production  # noqa: E402
from arc.select_solver import fg_objects  # noqa: E402  (also puts ARCKG on path)
from ARCKG.grid import Grid  # noqa: E402
from arc.dsl import (context, resolve_arguments, build_answer, grid_bg,  # noqa: E402
                     ranked_hypotheses, build_from_hypothesis)


def _lone(objs):
    return objs[0] if len(objs) == 1 else None


def _target_and_others(in_objs, out_obj):
    """Identify the target object (the one that becomes the output, matched by
    colour) and the OTHER objects (markers the relation expressions can use)."""
    if out_obj is not None:
        by_color = [o for o in in_objs if o["color"] == out_obj["color"]]
        if len(by_color) == 1:
            tin = by_color[0]
            return tin, [o for o in in_objs if o is not tin]
    if len(in_objs) == 1:
        return in_objs[0], []
    return None, []


# to_json keys whose LIST value is kept WHOLE (one compact hashable value) instead
# of exploding into indexed sub-nodes (.0 .1 .2 …). contents/shape = 2D grid image;
# coordinate = list of [row,col] — the intelligence reads it as one coordinate list,
# not as separate cells, so it renders as a single `[[r,c],…]` leaf (사용자 요청 2026-07-08).
_WHOLE_VALUED = {"contents", "shape", "coordinate"}


def _tup(v):
    return tuple(_tup(x) for x in v) if isinstance(v, list) else v


def _load_value(wm, nid, attr, val):
    """Recursively load one to_json value as WMEs (dict/list -> nested sub-node;
    scalar -> leaf). 2D-grid props + coordinate stay whole (see _WHOLE_VALUED)."""
    if attr in _WHOLE_VALUED and isinstance(val, list):
        wm.add(nid, attr, _tup(val))
    elif isinstance(val, dict):
        sub = f"{nid}.{attr}"
        wm.add(nid, attr, sub)
        for k, v in val.items():
            _load_value(wm, sub, str(k), v)
    elif isinstance(val, list):
        sub = f"{nid}.{attr}"
        wm.add(nid, attr, sub)
        for i, item in enumerate(val):
            _load_value(wm, sub, str(i), item)
    else:
        wm.add(nid, attr, val)


def _fg_obj(o):
    return next((c for c, present in o.to_json()["color"].items() if present), 0) != 0


def _load_node(wm, node):
    """Load ONE ARCKG node LAZILY (mirrors agent/wm.py::load_node): its to_json()
    properties (recursively) + structural edges as id REFERENCES only. Children
    are NOT loaded here -- they fill in when visited (P1 lazy / descent)."""
    nid = node.node_id
    if wm.contains(nid, "type", type(node).__name__.lower()):
        return                                      # already loaded (dedup)
    wm.add(nid, "type", type(node).__name__.lower())
    for k, v in node.to_json().items():
        _load_value(wm, nid, k, v)
    for ka, edge in (("example_pairs", "example"), ("test_pairs", "test")):
        for c in getattr(node, ka, []) or []:
            wm.add(nid, edge, c.node_id)            # edge = id ref (child not loaded)
    for attr, edge in (("input_grid", "input"), ("output_grid", "output")):
        c = getattr(node, attr, None)
        if c is not None:
            wm.add(nid, edge, c.node_id)
    for o in getattr(node, "objects", None) or []:
        if _fg_obj(o):
            wm.add(nid, "object", o.node_id)


def build_arckg(tid, task):
    """Build the ARCKG Python hierarchy with the real node-ID convention:
    TASK = T{tid}; example pairs T{tid}.P0,P1,... ; TEST pairs T{tid}.Pa,Pb,... ;
    grids .G0(input)/.G1(output) ; objects .O{i}."""
    from ARCKG.pair import Pair
    from ARCKG.task import Task
    T = f"T{tid}"
    ex, test = [], []
    for i, p in enumerate(task["train"]):
        gi = Grid(f"{T}.P{i}.G0", p["input"]); gi.extract_objects()
        go = Grid(f"{T}.P{i}.G1", p["output"]); go.extract_objects()
        ex.append(Pair(f"{T}.P{i}", gi, go))
    for j, tp in enumerate(task["test"]):
        Pid = f"{T}.P{chr(ord('a') + j)}"            # test pairs: Pa, Pb, ...
        gi = Grid(f"{Pid}.G0", tp["input"]); gi.extract_objects()
        test.append(Pair(Pid, gi, None))             # test has no output grid (P5)
    return Task(tid, ex, test)                        # node_id = "T{tid}"


def _visit_children(wm, node):
    """Lazily load a node's immediate children (used when an operator visits)."""
    for c in (list(getattr(node, "example_pairs", []) or [])
              + list(getattr(node, "test_pairs", []) or [])):
        _load_node(wm, c)
        for g in (getattr(c, "input_grid", None), getattr(c, "output_grid", None)):
            if g is not None:
                _load_node(wm, g)
                for o in g.objects or []:
                    if _fg_obj(o):
                        _load_node(wm, o)


def inject_task(agent):
    """ARC input function (mirrors ARC-solver agent/io.py::inject_arc_task). Runs
    at the INPUT phase. The environment delivers ONLY the raw, unparsed task onto
    ^io.input-link: the task node's identity (^type, ^name) and its RAW data --
    the literal ARC task dict as a SINGLE value on ^raw (NOT structured into
    sub-nodes; long, so the dashboard shows it truncated `{"train": [...`). The
    task STRUCTURE -- properties (^roles) and which pairs hang under it
    (^example/^test edges) -- is deliberately NOT built here; the `observe`
    operator parses ^raw into structured WM (P1: read the input-link, then frame).
    Pair/grid/object contents load even later, on visit (compare)."""
    kg = agent.kg
    if kg.get("arckg_root") is not None:
        return                                  # already injected (idempotent)
    tid = getattr(agent, "task_id", "0a")
    root = build_arckg(tid, agent.task)
    kg["arckg_root"] = root
    nid = root.node_id
    agent.add_input_wme("I2", "task", nid)             # input-link -> Task node
    agent.add_input_wme(nid, "type", "task")           # identity only
    agent.add_input_wme(nid, "name", tid)
    agent.add_input_wme(nid, "raw", json.dumps(agent.task))   # the literal task dict


def setup_arc_agent(task, tid="0a", record=False):
    """Build an Agent wired for ARC: io structure + the inject_task input function."""
    ag = Agent(PRODUCTIONS, operator_bodies=OPERATOR_BODIES, record=record, io=True)
    ag.task = task
    ag.task_id = tid
    ag.kg = {}
    ag.input_functions.append(inject_task)
    return ag


def _op_observe(agent):
    """observe: READ the raw Task on the input-link and ELABORATE it into WM --
    the task node's properties (^roles) + which pairs hang under it (^example /
    ^test edges). This is the FRAMING step: it reveals the task's structure but
    does NOT yet descend into pair/grid contents (compare does that). Then it
    identifies target objects and refines the goal."""
    task = agent.task
    kg = agent.kg
    root = kg.get("arckg_root")
    if root is not None:                               # elaborate task structure
        nid = root.node_id
        for k, v in root.to_json().items():            # properties: ^roles sub-node
            _load_value(agent.wm, nid, k, v)
        for ka, edge in (("example_pairs", "example"), ("test_pairs", "test")):
            for c in getattr(root, ka, []) or []:
                agent.wm.add(nid, edge, c.node_id)     # which pairs exist (edges)
    kg["pairs"] = []
    tcolors = set()
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        tout = _lone(fg_objects(p["output"], f"P{i}.G1"))
        tin, others = _target_and_others(ins, tout)
        kg["pairs"].append({"in_raw": p["input"], "out_raw": p["output"],
                            "tin": tin, "tout": tout, "others": others})
        if tin:
            tcolors.add(tin["color"])
    tp = task["test"][0]
    test_objs = fg_objects(tp["input"], "Pa.G0")
    test_obj = _pick_target(test_objs, tcolors)
    kg["test_in_raw"] = tp["input"]
    kg["test_obj"] = test_obj
    kg["test_others"] = [o for o in test_objs if o is not test_obj] if test_obj else []
    kg["test_dims"] = (len(tp["output"]), len(tp["output"][0]))
    # NOTE: the ^observed result flag is written by the apply-observe PRODUCTION
    # (o-support); this body only does the ARCKG computation (the RHS function).


def _op_compare(agent):
    kg = agent.kg
    if kg.get("arckg_root"):
        _visit_children(agent.wm, kg["arckg_root"])   # lazy: load pairs/grids/objects on visit
    samples = []
    if not all(pr["tin"] and pr["tout"] for pr in kg["pairs"]):
        kg["samples"] = []                  # not single-object -> nothing to compare
        return
    for pr in kg["pairs"]:
        out_cells = sorted(pr["tout"]["cells"])
        out_dims = (len(pr["out_raw"]), len(pr["out_raw"][0]))
        samples.append({
            "ctx": context(pr["tin"], pr["in_raw"], out_dims, others=pr["others"]),
            "out_coord": out_cells[0],
            "out_color": pr["tout"]["color"],
            "out_size": out_dims,
            "out_bg": grid_bg(pr["out_raw"]),
        })
    kg["samples"] = samples


def _op_generalize(agent):
    kg = agent.kg
    args = resolve_arguments(kg["samples"]) if kg.get("samples") else {}
    kg["args"] = args
    for arg, (_fn, name) in args.items():
        agent.wm.add("S1", f"expr-{arg}", name or "?")   # data-dependent display WMEs


def _op_compose(agent):
    kg = agent.kg
    answer = None
    if kg.get("test_obj") and kg.get("args"):
        ctx = context(kg["test_obj"], kg["test_in_raw"], kg["test_dims"],
                      others=kg.get("test_others"))
        answer = build_answer(kg["args"], ctx)
    if answer is None:
        agent.wm.add("S1", "declined", "yes")   # data-dependent: only the body knows
    else:
        kg["answer"] = answer
        agent.add_output_wme("answer", tuple(tuple(r) for r in answer))  # -> output-link
    # ^answer-ready result flag is written by the apply-compose PRODUCTION.


# operator NAME -> RHS-function body (the ARCKG/DSL computation). submit has no
# computation: the apply-submit production alone writes ^done.
OPERATOR_BODIES = {
    "observe": _op_observe, "compare": _op_compare,
    "generalize": _op_generalize, "compose": _op_compose,
}


# Each operator is a NAMED OBJECT in WM. propose-<n> mints a fresh operator id
# <o> (the kernel gensyms it -> O1, O2, ...) and asserts (<o> ^name <n>) plus the
# acceptable preference (S1 ^operator <o> +). So the object id is opaque (like
# SOAR's O1) and its identity is carried by ^name. The decision installs the bare
# (S1 ^operator <o>); apply-<n> then fires on that SELECTED operator and writes
# the o-supported result flag. The Python body above is the RHS-function doing
# the heavy ARCKG/DSL computation.
# Soar names productions <role>*<operator> (e.g. blocks-world*propose*move-block,
# *apply*move-block*remove-old-ontop) -- '*' joins role/operator/variant.
def _propose(name, conds):
    # Soar convention (manual blocksworld): the operator ACCEPTABLE preference
    # (<s> ^operator <o> +) comes FIRST, then the operator object's augmentations
    # (<o> ^name ...). RHS order is functionally irrelevant (actions fire as a set),
    # but this matches the standard reading "propose the operator, then describe it".
    return Production(f"propose*{name}", conds,
                      [Action("S1", "operator", "<o>", "+"), Action("<o>", "name", name)])


def _apply(name, result_attr):
    return Production(f"apply*{name}",
                      [Cond("S1", "operator", "<o>"), Cond("<o>", "name", name)],
                      [Action("S1", result_attr, "yes")])


PRODUCTIONS = [
    _propose("observe",    [Cond("I2", "task", "<t>"), Cond("S1", "observed", "<x>", negated=True)]),
    _propose("compare",    [Cond("S1", "observed", "yes"), Cond("S1", "compared", "<x>", negated=True)]),
    _propose("generalize", [Cond("S1", "compared", "yes"), Cond("S1", "schema-ready", "<x>", negated=True)]),
    _propose("compose",    [Cond("S1", "schema-ready", "yes"), Cond("S1", "answer-ready", "<x>", negated=True)]),
    _propose("submit",     [Cond("S1", "answer-ready", "yes"), Cond("S1", "done", "<x>", negated=True)]),
    _apply("observe", "observed"),
    _apply("compare", "compared"),
    _apply("generalize", "schema-ready"),
    _apply("compose", "answer-ready"),
    _apply("submit", "done"),
]


def solve(task, record=False, tid="0a"):
    ag = setup_arc_agent(task, tid, record)     # io + inject_task input function
    for _ in range(10):
        ag.step()                               # step() runs the INPUT phase first
        if ag.wm.contains("S1", "done", "yes"):
            break
    answer = ag.kg.get("answer")
    exprs = {a: n for a, (f, n) in (ag.kg.get("args") or {}).items()}
    return {"answer": answer, "exprs": exprs,
            "correct": answer == task["test"][0]["output"], "trace": ag.trace if record else None}


def candidates(task, n: int = 3):
    """Ranked candidate ANSWERS (one per attempt), each a list of grids covering
    ALL test pairs. A hypothesis is one rule for the whole task, applied to every
    test input. Ambiguous tasks yield several answers to try across the 3 submits
    (the wiki's 'wrong -> reject preference -> next candidate')."""
    pairs = []
    tcolors = set()
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        tout = _lone(fg_objects(p["output"], f"P{i}.G1"))
        tin, others = _target_and_others(ins, tout)
        if not tin or not tout:
            return []
        tcolors.add(tin["color"])
        dims = (len(p["output"]), len(p["output"][0]))
        pairs.append({"ctx": context(tin, p["input"], dims, others=others),
                      "out_coord": sorted(tout["cells"])[0], "out_color": tout["color"],
                      "out_size": dims, "out_bg": grid_bg(p["output"])})
    # the test contexts (one per test pair) -- same target-by-colour rule
    test_ctxs = []
    for tp in task["test"]:
        objs = fg_objects(tp["input"], "PT.G0")
        if len(tcolors) == 1:
            m = [o for o in objs if o["color"] == next(iter(tcolors))]
            tobj = m[0] if len(m) == 1 else _lone(objs)
        else:
            tobj = _lone(objs)
        if not tobj:
            return []
        others = [o for o in objs if o is not tobj]
        test_ctxs.append(context(tobj, tp["input"],
                                 (len(tp["output"]), len(tp["output"][0])), others=others))

    out, seen = [], set()
    for hyp in ranked_hypotheses(pairs):
        answer = [build_from_hypothesis(hyp, ctx) for ctx in test_ctxs]
        if any(g is None for g in answer):
            continue
        key = tuple(tuple(tuple(r) for r in g) for g in answer)
        if key in seen:
            continue
        seen.add(key)
        out.append({"grid": answer, "position": hyp["position"],
                    "color": hyp["color"], "score": hyp["score"]})
        if len(out) >= n:
            break
    return out


def _build_train(task):
    """Train samples + the consistent target colour(s). None if not single-object."""
    pairs, tcolors = [], set()
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        tout = _lone(fg_objects(p["output"], f"P{i}.G1"))
        tin, others = _target_and_others(ins, tout)
        if not tin or not tout:
            return None
        tcolors.add(tin["color"])
        dims = (len(p["output"]), len(p["output"][0]))
        pairs.append({"ctx": context(tin, p["input"], dims, others=others),
                      "out_coord": sorted(tout["cells"])[0], "out_color": tout["color"],
                      "out_size": dims, "out_bg": grid_bg(p["output"])})
    return pairs, tcolors


def _pick_target(objs, tcolors):
    if len(tcolors) == 1:
        m = [o for o in objs if o["color"] == next(iter(tcolors))]
        return m[0] if len(m) == 1 else _lone(objs)
    return _lone(objs)


def candidate_grids(task, test_index, n: int = 3):
    """Ranked candidate grids for ONE test pair (solved one at a time, with its
    own retries). A hypothesis is a task-level rule applied to this test input."""
    built = _build_train(task)
    if built is None:
        return []
    pairs, tcolors = built
    tp = task["test"][test_index]
    objs = fg_objects(tp["input"], "PT.G0")
    tobj = _pick_target(objs, tcolors)
    if not tobj:
        return []
    others = [o for o in objs if o is not tobj]
    ctx = context(tobj, tp["input"], (len(tp["output"]), len(tp["output"][0])), others=others)
    out, seen = [], set()
    for hyp in ranked_hypotheses(pairs):
        g = build_from_hypothesis(hyp, ctx)
        if g is None:
            continue
        key = tuple(tuple(r) for r in g)
        if key in seen:
            continue
        seen.add(key)
        out.append(g)
        if len(out) >= n:
            break
    return out


def predict(task):
    answers = []
    for tp in task["test"]:
        try:
            answers.append(solve({"train": task["train"], "test": [tp]})["answer"])
        except Exception:
            answers.append(None)
    return answers


def _bench(name):
    from arc.dataset import list_tasks, load_task
    solved, n = 0, 0
    for tid, path in list_tasks(name):
        n += 1
        try:
            if solve(load_task(path))["correct"]:
                solved += 1
        except Exception:
            pass
    return solved, n


def _bench_retry(name, attempts=3):
    """Solved if any of the top-`attempts` candidate ANSWERS (all test pairs)
    matches the ground truth -- the honest 3-submit measure."""
    from arc.dataset import list_tasks, load_task
    solved, n = 0, 0
    for tid, path in list_tasks(name):
        n += 1
        t = load_task(path)
        gt = [tp["output"] for tp in t["test"]]
        try:
            cs = candidates(t, attempts)
        except Exception:
            cs = []
        if any(c["grid"] == gt for c in cs[:attempts]):
            solved += 1
    return solved, n


if __name__ == "__main__":
    for ds in ("easy_a", "easy"):
        s, n = _bench(ds)
        sr, _ = _bench_retry(ds, 3)
        print(f"{ds:8} 1-submit {s}/{n}   3-submit {sr}/{n}")
    # show the resolved expressions for one task
    from arc.dataset import list_tasks, load_task
    r = solve(load_task(list_tasks("easy_a")[0][1]))
    print("\neasy000a resolved argument expressions:")
    for arg, expr in r["exprs"].items():
        print(f"  {arg:9} = {expr}")
