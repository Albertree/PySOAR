"""AST-based anti-unification (prototype).

Idea (user, 2026-07-13): represent each per-pair program's CORE as a nested-dict AST, so
finding the common structure across pairs = structural anti-unification (walk the two
ASTs in parallel → COMM nodes kept, DIFF leaves become holes). Then resolve each hole
using ONLY native object/pixel PROPERTY & RELATION COMM/DIFF + membership (소속) — no
invented concept DSL, no prettily-named new relation. The selection reason is expressed
as a logical formula over same/different of already-represented properties/relations.

Native vocabulary only (ARCKG OBJECT props: color, size(area), coordinate, shape; PIXEL:
color, coordinate; relations = compare COMM/DIFF, number-DIFF refined to greater/less;
membership = pixel∈object, object∈grid). Concepts like holes/parity/shape_topo are NOT
used (those are inventions — an honest abstraction-gap when a task needs them).
"""
from __future__ import annotations

import json

from debugger.reports.abstraction import per_pair_objects, Obj, Pair
from arc.focus_solver import objects_of

VAR = "‹VAR›"


# ── generic structural anti-unification over nested dict/list/scalar ───────
def anti_unify(nodes, path=(), holes=None):
    """given the SAME-shaped ASTs of N pairs, return a skeleton where positions that agree
    across all pairs are kept (COMM) and positions that differ become VAR (DIFF); the
    differing value-tuples are collected in `holes` keyed by path."""
    if holes is None:
        holes = {}
    n0 = nodes[0]
    if all(n == n0 for n in nodes):
        return n0, holes
    if all(isinstance(n, dict) for n in nodes) and all(set(n) == set(n0) for n in nodes):
        return {k: anti_unify([n[k] for n in nodes], path + (k,), holes)[0] for k in n0}, holes
    if all(isinstance(n, list) for n in nodes) and all(len(n) == len(n0) for n in nodes):
        return [anti_unify([n[i] for n in nodes], path + (i,), holes)[0]
                for i in range(len(n0))], holes
    holes[path] = [n for n in nodes]          # DIFF leaf → hole (records observed values)
    return VAR, holes


# ── native property / relation helpers (COMM/DIFF + order + membership) ────
def color_group(o, pair):
    """membership + colour-COMM: the objects whose colour is COMM with o (same-colour set)."""
    return [q for q in pair.allobjs if q.color == o.color]


def size_order_count(o, siblings):
    """relational profile from native size-DIFF refined to greater/less, then COUNTED:
    #{siblings s : size(o) > size(s)}. '가장 큼' = count == len-1 (exceeds all). No rank concept."""
    return sum(1 for s in siblings if s is not o and o.size > s.size)


def adjacent_diff_color(o, pair):
    """object relation via pixel adjacency + membership: the single colour COMM among the
    objects 4-adjacent to o and DIFF in colour from o (None if not unique)."""
    cols = {q.color for q in pair.adjacency()[o] if q.color != o.color}
    return next(iter(cols)) if len(cols) == 1 else None


# native relational profiles the resolver may try (all expressed in COMM/DIFF + membership):
PROFILES = [
    ("size-order-count in colour-group",
     lambda o, p: size_order_count(o, color_group(o, p))),
    ("shape-COMM class",
     lambda o, p: tuple(sorted(o.shape))),                 # native 'shape' property, COMM key
    ("adjacent-DIFF-colour object's colour",
     lambda o, p: adjacent_diff_color(o, p)),
]


# ── per-pair program AST ───────────────────────────────────────────────────
def pair_ast(pair, sel_color):
    """the core of one pair's program as a nested dict. Selected objects (colour-COMM =
    sel_color) are each recoloured; the body is a coloring on the object's own coordinate
    (pixel membership), with a concrete colour leaf per role."""
    outmap = {id(o): oc for (o, oc) in pair.recolored}
    sel = [o for o in pair.allobjs if o.color == sel_color and id(o) in outmap]
    # order the selected objects by a native relational profile so roles align across pairs
    roles = sorted(sel, key=lambda o: size_order_count(o, color_group(o, pair)))
    return {
        "for_each": {"member_of": "objects_of(input_grid)",
                     "where": {"native": "color", "rel": "COMM", "value": sel_color}},
        "do": {"op": "coloring",
               "target": {"native": "coordinate", "of": "o"},   # o의 픽셀 소속 = o.coord
               "color": [outmap[id(o)] for o in roles]},        # per-role colour (aligned)
    }


# ── resolve a hole with native COMM/DIFF logic ─────────────────────────────
def resolve_color(pairs, sel_color, task):
    """for the colour hole: search native relational PROFILES; a candidate whose
    profile→colour map is COMM (consistent) across pairs is accepted ONLY if it also
    reproduces every train output when EXECUTED (gate against shape-memorisation etc.).
    Returns (profile_name, table) or None (honest abstraction-gap)."""
    for name, prof in PROFILES:
        table, ok = {}, True
        for p in pairs:
            outmap = {id(o): oc for (o, oc) in p.recolored}
            for o in p.allobjs:
                if o.color != sel_color or id(o) not in outmap:
                    continue
                v = prof(o, p)
                if v is None:
                    ok = False; break
                if v in table and table[v] != outmap[id(o)]:
                    ok = False; break
                table[v] = outmap[id(o)]
            if not ok:
                break
        if ok and table and all(apply_ast(ex["input"], sel_color, name, table) == ex["output"]
                                for ex in task["train"]):
            return name, table
    return None, None


def apply_ast(grid, sel_color, profile_name, table):
    prof = dict((n, f) for n, f in PROFILES)[profile_name]
    objs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
    pair = Pair(objs, [], len(grid), len(grid[0]))
    out = [row[:] for row in grid]
    for o in objs:
        if o.color != sel_color:
            continue
        col = table.get(prof(o, pair))
        if col is None:
            return None
        for (r, c) in o.cells:
            out[r][c] = col
    return out


def selection_reason(pairs, sel_color):
    """express WHY these objects are selected, purely in COMM/DIFF of native properties +
    membership — no invented predicate."""
    # largest object (max size) — described only as 'the object DIFF in colour, size greater than all'
    return (f"o ∈ objects_of(input_grid)  ∧  color(o) COMM {sel_color}   "
            f"(그 색은 pair마다 COMM; 최대크기 배경 객체와는 color DIFF)")


def run(task, tid):
    pairs = per_pair_objects(task)
    if not any(p.recolored for p in pairs):
        return {"tid": tid, "verdict": "NA", "why": "no recolor objects"}
    sel = {o.color for p in pairs for (o, _oc) in p.recolored}
    if len(sel) != 1:
        return {"tid": tid, "verdict": "NA", "why": f"selected span colors {sorted(sel)}"}
    sel_color = next(iter(sel))
    asts = [pair_ast(p, sel_color) for p in pairs]
    skel, holes = anti_unify(asts)
    pname, table = resolve_color(pairs, sel_color, task)
    verdict, tr, te = "IMPASSE", [], None
    if pname:
        tr = [apply_ast(ex["input"], sel_color, pname, table) == ex["output"] for ex in task["train"]]
        if task.get("test") and "output" in task["test"][0]:
            te = apply_ast(task["test"][0]["input"], sel_color, pname, table) == task["test"][0]["output"]
        verdict = "SOLVE" if all(tr) and te is not False else ("OVERFIT" if all(tr) else "PARTIAL")
    return {"tid": tid, "verdict": verdict, "sel_color": sel_color, "asts": asts, "skel": skel,
            "holes": holes, "profile": pname, "table": table, "reason": selection_reason(pairs, sel_color),
            "train_ok": tr, "test_ok": te}


if __name__ == "__main__":
    from arc.focus_solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    for tid in ("08ed6ac7", "845d6e51", "868de0fa", "009d5c81"):
        r = run(tasks[tid], tid)
        print("\n" + "=" * 70 + f"\n{r['verdict']:8s} {tid}\n" + "=" * 70)
        if r["verdict"] in ("NA",):
            print("  " + r["why"]); continue
        print("  per-pair program AST (pair 0):")
        print("   " + json.dumps(r["asts"][0], ensure_ascii=False, indent=2).replace("\n", "\n   "))
        print("\n  구조 anti-unify → 공통 뼈대 (COMM 유지, DIFF=‹VAR›):")
        print("   " + json.dumps(r["skel"], ensure_ascii=False, indent=2).replace("\n", "\n   "))
        print(f"\n  DIFF 홀(경로→pair별 관측): {dict(r['holes'])}")
        print(f"  선택 근거 (COMM/DIFF): {r['reason']}")
        if r["profile"]:
            print(f"  홀 resolve (native 관계프로파일): color = table[{r['profile']}]")
            print(f"                         table = {r['table']}   (pair간 COMM)")
            print(f"  train_ok={r['train_ok']}  test_ok={r['test_ok']}")
        else:
            print("  홀 resolve: 실패 — native property/relation COMM/DIFF 로 색이 안 정해짐")
            print("             (parity 등 발명개념 필요 = 정직한 abstraction-gap)")
