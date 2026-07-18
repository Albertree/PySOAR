"""
expr_solver -- ARCKG-builder utilities shared by the focus/move path.

Historically this module also held a hand-rolled single-object DSL solver
(observe/compare/generalize/compose operators + PRODUCTIONS + solve/predict).
That legacy pipeline has been retired (superseded by the rule-driven
focus_solver + procedural_memory operators); what remains is the ARCKG
construction machinery those operators -- and most of arbor/ -- still build
on: build_arckg() (Task/Pair/Grid hierarchy from a raw ARC task dict) and the
recursive to_json() -> WME loader (_load_value / _tup / _WHOLE_VALUED).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arbor.perception.arckg.grid import Grid  # noqa: E402


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


def build_arckg(tid, task):
    """Build the ARCKG Python hierarchy with the real node-ID convention:
    TASK = T{tid}; example pairs T{tid}.P0,P1,... ; TEST pairs T{tid}.Pa,Pb,... ;
    grids .G0(input)/.G1(output) ; objects .O{i}."""
    from arbor.perception.arckg.pair import Pair
    from arbor.perception.arckg.task import Task
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
