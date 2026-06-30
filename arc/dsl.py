"""
dsl -- ARBOR DSL: 2 frozen transformations (make_grid, coloring) + argument
EXPRESSIONS over property/relation/util, with a resolver that turns a SPECIFIC
per-pair value into the most GENERAL expression consistent across train pairs.

This is the wiki's core insight (arbor-dsl-taxonomy): every ARC output is built
by make_grid + coloring; the search space is the *argument expression tree*, not
the transformation tree. A raw value like position (5,5) is not kept literal --
the resolver finds an expression that produces it generally
(e.g. corner-br = (H-1, W-1), or coord_of(obj)+displacement).

transformation = make_grid / coloring (imported from ARC-solver, frozen, 2 only).
property/util  = imported from ARC-solver (color_of, coordinate_of, ...).
expressions    = composed here; resolved by least-generality-rank consistency.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

_ARC = os.path.expanduser("~/Desktop/ARC-solver")
if _ARC not in sys.path:
    sys.path.insert(0, _ARC)

from procedural_memory.DSL.transformation import make_grid, coloring  # noqa: E402  frozen 2


# -- context: the input-side facts an expression may reference -----------------
def grid_bg(raw):
    flat = [v for row in raw for v in row]
    return Counter(flat).most_common(1)[0][0] if flat else 0


def context(target_obj, in_raw, out_dims, others=None):
    """Facts available to argument expressions for one (pair, target object).
    ``others`` = the OTHER input objects, so RELATION expressions can derive an
    argument from another node (e.g. position = coord_of(the marker)."""
    cells = sorted(target_obj["cells"])
    H, W = out_dims
    return {
        "obj_coord": cells[0],        # single-cell target -> its (r,c)
        "obj_color": target_obj["color"],
        "obj_cells": frozenset(target_obj["cells"]),
        "H": H, "W": W,
        "in_bg": grid_bg(in_raw),
        "in_size": (len(in_raw), len(in_raw[0])),
        "others": [{"color": o["color"], "coord": sorted(o["cells"])[0]}
                   for o in (others or [])],
    }


# -- argument expression templates --------------------------------------------
# Each: builder(samples) -> (eval_fn, name) if consistent across ALL samples,
# else None. samples = [(ctx, target_value), ...]. Lower rank = more general
# (preferred). The whole point: prefer a general expression over a literal.

def _pos_templates():
    def identity(s):
        if all(c["obj_coord"] == t for c, t in s):
            return (lambda c: c["obj_coord"]), "coord_of(obj)"
    def delta(s):
        ds = {(t[0] - c["obj_coord"][0], t[1] - c["obj_coord"][1]) for c, t in s}
        if len(ds) == 1:
            d = next(iter(ds))
            return (lambda c, d=d: (c["obj_coord"][0] + d[0], c["obj_coord"][1] + d[1])), \
                   f"coord_of(obj)+{d}"
    def corner(name, fn):
        def b(s):
            if all(t == fn(c) for c, t in s):
                return (lambda c, fn=fn: fn(c)), name
        return b
    def diag(s):
        def dg(c):
            r, col = c["obj_coord"]
            while r < c["H"] - 1:
                r += 1; col += 1
            return (r, min(col, c["W"] - 1))
        if all(t == dg(c) for c, t in s):
            return (lambda c: dg(c)), "diag-gravity(obj)"
    def literal(s):
        ts = {t for c, t in s}
        if len(ts) == 1:
            v = next(iter(ts))
            return (lambda c, v=v: v), f"literal{v}"
    def relation(s):
        # position = coord_of(another object) [+ delta]  (RELATION expression)
        for sel, sname in _other_selectors(s):
            fn = (lambda c, sel=sel: (lambda o: o["coord"] if o else None)(sel(c)))
            if all(fn(c) == t for c, t in s):
                return fn, f"coord_of({sname})"
            o0 = sel(s[0][0]) if s else None
            if o0:
                d = (s[0][1][0] - o0["coord"][0], s[0][1][1] - o0["coord"][1])
                fnd = (lambda c, sel=sel, d=d:
                       (lambda o: (o["coord"][0] + d[0], o["coord"][1] + d[1]) if o else None)(sel(c)))
                if all(fnd(c) == t for c, t in s):
                    return fnd, f"coord_of({sname})+{d}"
    return [
        (0, identity), (1, delta), (1, relation),
        (2, corner("corner-tl", lambda c: (0, 0))),
        (2, corner("corner-br", lambda c: (c["H"] - 1, c["W"] - 1))),
        (2, corner("corner-tr", lambda c: (0, c["W"] - 1))),
        (2, corner("corner-bl", lambda c: (c["H"] - 1, 0))),
        (3, diag), (4, literal),
    ]


def _scalar_templates(ctx_key, name):
    def from_prop(s):
        if all(c[ctx_key] == t for c, t in s):
            return (lambda c: c[ctx_key]), name
    def literal(s):
        ts = {t for c, t in s}
        if len(ts) == 1:
            v = next(iter(ts))
            return (lambda c, v=v: v), f"literal({v})"
    def relation(s):  # color = color_of(another object)  (RELATION expression)
        for sel, sname in _other_selectors(s):
            fn = (lambda c, sel=sel: (lambda o: o["color"] if o else None)(sel(c)))
            if all(fn(c) == t for c, t in s):
                return fn, f"color_of({sname})"
    tmpls = [(0, from_prop), (4, literal)]
    if ctx_key == "obj_color":
        tmpls.insert(1, (1, relation))
    return tmpls


def _size_templates():
    def from_input(s):
        if all((c["H"], c["W"]) == (c["in_size"][0], c["in_size"][1]) for c, _ in s):
            return (lambda c: {"height": c["in_size"][0], "width": c["in_size"][1]}), "size_of(input)"
    def literal(s):
        ts = {t for _, t in s}
        if len(ts) == 1:
            v = next(iter(ts))
            return (lambda c, v=v: {"height": v[0], "width": v[1]}), f"literal{v}"
    return [(0, from_input), (4, literal)]


def resolve(samples, templates):
    """Pick the most general (lowest-rank) expression consistent across samples."""
    best = None
    for rank, builder in templates:
        r = builder(samples)
        if r is not None:
            fn, name = r
            if best is None or rank < best[0]:
                best = (rank, fn, name)
    return (best[1], best[2]) if best else (None, None)


# -- build an answer with make_grid + coloring + resolved expressions ----------
def resolve_arguments(pairs):
    """pairs: [{ctx, out_coord, out_color, out_size, out_bg}]. Returns the
    resolved expression for each argument (position/color/size/fill)."""
    pos_fn, pos_name = resolve([(p["ctx"], p["out_coord"]) for p in pairs], _pos_templates())
    col_fn, col_name = resolve([(p["ctx"], p["out_color"]) for p in pairs],
                               _scalar_templates("obj_color", "color_of(obj)"))
    size_fn, size_name = resolve([(p["ctx"], p["out_size"]) for p in pairs], _size_templates())
    bg_fn, bg_name = resolve([(p["ctx"], p["out_bg"]) for p in pairs],
                             _scalar_templates("in_bg", "background(input)"))
    return {
        "position": (pos_fn, pos_name), "color": (col_fn, col_name),
        "size": (size_fn, size_name), "fill": (bg_fn, bg_name),
    }


def _other_selectors(samples):
    """Consistent ways to pick ANOTHER object (the basis of relation expressions).
    Yields (select_fn(ctx)->other|None, name)."""
    sels = []
    if samples and all(len(c["others"]) == 1 for c, _ in samples):
        sels.append((lambda c: c["others"][0] if len(c["others"]) == 1 else None, "other"))
    if samples:
        common = set.intersection(*[{o["color"] for o in c["others"]} for c, _ in samples])
        for K in sorted(common):
            def sel(c, K=K):
                m = [o for o in c["others"] if o["color"] == K]
                return m[0] if len(m) == 1 else None
            sels.append((sel, f"other:color={K}"))
    return sels


def _relation_pos_candidates(samples):
    """RELATION position expressions: derive position from another object."""
    cands = []
    for sel, sname in _other_selectors(samples):
        cands.append(((lambda c, sel=sel: (lambda o: o["coord"] if o else None)(sel(c))),
                      f"coord_of({sname})", 1))
        o0 = sel(samples[0][0]) if samples else None
        if o0:
            t0 = samples[0][1]
            d = (t0[0] - o0["coord"][0], t0[1] - o0["coord"][1])
            cands.append(((lambda c, sel=sel, d=d:
                           (lambda o: (o["coord"][0] + d[0], o["coord"][1] + d[1]) if o else None)(sel(c))),
                          f"coord_of({sname})+{d}", 2))
    return cands


def _relation_color_candidates(samples):
    """RELATION color expression: recolor to another object's colour."""
    return [((lambda c, sel=sel: (lambda o: o["color"] if o else None)(sel(c))),
             f"color_of({sname})", 1)
            for sel, sname in _other_selectors(samples)]


def _pos_candidate_fns(samples):
    """All position expressions, each scored by how many pairs it fits."""
    cands = []
    for rank, fn, name in [
        (0, lambda c: c["obj_coord"], "coord_of(obj)"),
        (2, lambda c: (0, 0), "corner-tl"),
        (2, lambda c: (c["H"] - 1, c["W"] - 1), "corner-br"),
        (2, lambda c: (0, c["W"] - 1), "corner-tr"),
        (2, lambda c: (c["H"] - 1, 0), "corner-bl"),
    ]:
        cands.append((fn, name, rank))
    for c0, t0 in samples:
        d = (t0[0] - c0["obj_coord"][0], t0[1] - c0["obj_coord"][1])
        cands.append(((lambda c, d=d: (c["obj_coord"][0] + d[0], c["obj_coord"][1] + d[1])),
                      f"coord_of(obj)+{d}", 1))
    cands += _relation_pos_candidates(samples)            # relation expressions
    for _c0, t0 in samples:
        cands.append(((lambda c, v=t0: v), f"literal{t0}", 4))
    return _score(cands, samples)


def _scalar_candidate_fns(samples, ctx_key, prop_name):
    cands = [((lambda c: c[ctx_key]), prop_name, 0)]
    if ctx_key == "obj_color":
        cands += _relation_color_candidates(samples)       # relation expressions
    for _c0, t0 in samples:
        cands.append(((lambda c, v=t0: v), f"literal({t0})", 4))
    return _score(cands, samples)


def _score(cands, samples):
    """Attach n_consistent; dedup by name; sort by (most pairs, most general)."""
    seen, out = set(), []
    for fn, name, rank in cands:
        if name in seen:
            continue
        seen.add(name)
        n = sum(1 for c, t in samples if _safe(fn, c) == t)
        out.append({"fn": fn, "name": name, "rank": rank, "n": n})
    out.sort(key=lambda e: (-e["n"], e["rank"]))
    return out


def _safe(fn, c):
    try:
        return fn(c)
    except Exception:
        return None


def ranked_hypotheses(samples, n_pool: int = 8):
    """Rank full hypotheses (position, color, size, fill) by how many train pairs
    they fit, most general first. Returns the functions + names; the caller
    applies each hypothesis to EVERY test pair (a hypothesis is one rule for the
    whole task, not per-test-pair)."""
    pos = _pos_candidate_fns([(s["ctx"], s["out_coord"]) for s in samples])
    col = _scalar_candidate_fns([(s["ctx"], s["out_color"]) for s in samples],
                                "obj_color", "color_of(obj)")
    size = resolve([(s["ctx"], s["out_size"]) for s in samples], _size_templates())
    fill = resolve([(s["ctx"], s["out_bg"]) for s in samples],
                   _scalar_templates("in_bg", "background(input)"))
    if size[0] is None or fill[0] is None:
        return []
    combos = sorted(
        [(p, c) for p in pos for c in col],
        key=lambda pc: (-(pc[0]["n"] + pc[1]["n"]), pc[0]["rank"] + pc[1]["rank"]))
    return [{"size_fn": size[0], "fill_fn": fill[0], "pos_fn": p["fn"], "col_fn": c["fn"],
             "position": p["name"], "color": c["name"], "score": p["n"] + c["n"]}
            for p, c in combos[:n_pool]]


def build_from_hypothesis(hyp, ctx):
    """Build one grid for one test context via make_grid + coloring."""
    try:
        size = hyp["size_fn"](ctx)
        grid = make_grid(size, fill=hyp["fill_fn"](ctx))
        r, col = hyp["pos_fn"](ctx)
        if 0 <= r < size["height"] and 0 <= col < size["width"]:
            grid = coloring(grid, (r, col), hyp["col_fn"](ctx))
        return grid
    except Exception:
        return None


def build_answer(args, ctx):
    """Compose the output via the 2 frozen transformations using resolved args.
    Returns None (declines) if any argument could not be resolved to an
    expression -- e.g. contradictory training (same input, different output)."""
    if any(fn is None for fn, _name in args.values()):
        return None
    size = args["size"][0](ctx)
    fill = args["fill"][0](ctx)
    grid = make_grid(size, fill=fill)              # frozen transformation #1
    r, c = args["position"][0](ctx)
    color = args["color"][0](ctx)
    if 0 <= r < size["height"] and 0 <= c < size["width"]:
        grid = coloring(grid, (r, c), color)       # frozen transformation #2
    return grid
