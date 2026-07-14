"""Anti-unification of per-pair programs into a task-general solution (separate module).

Harness posture (ARBOR_HARNESS.md §0.5, §1-5, §2-2, §2-3):
  - `program`  = per-pair procedure (G0→G1), materialised by focus_solver's object path.
  - `solution` = task-general schema (variables), obtained here by anti-unifying the N
                 per-pair programs: align by ROLE (structure mapping), variabilise the
                 DIFF colour slot, then RESOLVE it by an ACTIVE binding SEARCH over a
                 broad but GENERIC vocabulary — object features (size / width / height /
                 hole-count(topology) / shape-equivalence / position) AND inter-object
                 relations (adjacent colour / nearest-different colour / container). Each
                 candidate is generated → verified across ALL pairs → rejected or kept;
                 rejects stay in the trace (§1-5: the winning binding is *found*, never
                 hand-supplied). Item comparison AND relation comparison (§2-2).

This module does NOT modify focus_solver. It reuses the solver's own correspondence
(`_fg_correspondence`) so the per-pair programs are the ones the object path produces;
it only adds the missing cross-pair generalisation (anti-unification) step.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from arc.expr_solver import build_arckg
from arc.focus_solver import index_arckg, _fg_correspondence, _obj_cc, objects_of


# ---------------------------------------------------------------------------
# 0. object with generic features (all derived from cells — no answer-specific info)
# ---------------------------------------------------------------------------
class Obj:
    def __init__(self, idx, color, cells):
        self.idx = idx
        self.color = color
        self.cells = tuple(sorted(map(tuple, cells)))
        self.size = len(self.cells)
        rs = [r for r, _ in self.cells]; cs = [c for _, c in self.cells]
        self.r0, self.c0, self.r1, self.c1 = min(rs), min(cs), max(rs), max(cs)
        self.height = self.r1 - self.r0 + 1
        self.width = self.c1 - self.c0 + 1
        self.topleft = self.cells[0]
        self.centroid = (sum(rs) / self.size, sum(cs) / self.size)
        self.shape = frozenset((r - self.r0, c - self.c0) for r, c in self.cells)
        self.shape_topo = _canonical_shape(self.shape)
        self.holes = _count_holes(self.cells, self.r0, self.c0, self.r1, self.c1)

    def __repr__(self):
        return f"Obj#{self.idx}(c{self.color},sz{self.size})"


def _canonical_shape(shape):
    """dihedral(8)-invariant canonical form → 'topologically/geometrically same' shape."""
    pts = list(shape)
    best = None
    for flip in (False, True):
        for rot in range(4):
            t = []
            for (r, c) in pts:
                if flip:
                    c = -c
                for _ in range(rot):
                    r, c = c, -r
                t.append((r, c))
            mr = min(r for r, _ in t); mc = min(c for _, c in t)
            norm = frozenset((r - mr, c - mc) for r, c in t)
            key = tuple(sorted(norm))
            if best is None or key < best:
                best = key
    return best


def _count_holes(cells, r0, c0, r1, c1):
    """# of enclosed empty regions inside the bbox not connected to the bbox border
    (a translation/scale-free topological feature: rings have 1, blobs 0)."""
    cellset = set(cells)
    H = r1 - r0 + 1; W = c1 - c0 + 1
    empt = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
            if (r, c) not in cellset}
    border = set()
    stack = [(r, c) for (r, c) in empt if r in (r0, r1) or c in (c0, c1)]
    while stack:
        p = stack.pop()
        if p in border or p not in empt:
            continue
        border.add(p)
        r, c = p
        stack += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
    inner = empt - border
    # count connected components of inner
    seen, holes = set(), 0
    for p in inner:
        if p in seen:
            continue
        holes += 1; st = [p]
        while st:
            q = st.pop()
            if q in seen or q not in inner:
                continue
            seen.add(q); r, c = q
            st += [(r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)]
    return holes


# ---------------------------------------------------------------------------
# 1. per-pair programs — reuse the solver's correspondence, invoked per pair
# ---------------------------------------------------------------------------
class Pair:
    def __init__(self, allobjs, recolored, H=0, W=0):
        self.allobjs = allobjs                 # every object of the input grid (context)
        self.recolored = recolored             # [(Obj, out_color)] — in-place recolours
        self.H, self.W = H, W
        self._adj = None

    def adjacency(self):
        """cell-level 4-adjacency between objects → {obj: set(neighbour objs)}."""
        if self._adj is not None:
            return self._adj
        cellmap = {}
        for o in self.allobjs:
            for cc in o.cells:
                cellmap[cc] = o
        adj = {o: set() for o in self.allobjs}
        for o in self.allobjs:
            for (r, c) in o.cells:
                for nb in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                    q = cellmap.get(nb)
                    if q is not None and q is not o:
                        adj[o].add(q)
        self._adj = adj
        return adj


def per_pair_objects(task):
    """For every train pair, return a Pair (allobjs + recolored) using the SAME
    correspondence the object path uses. No train[0] pinning."""
    root = build_arckg("t", task)
    idx = index_arckg(root)
    ag = SimpleNamespace(kg={"idx": idx, "arckg_root": root})
    pairs = []
    for k, pn in enumerate(root.example_pairs):
        g0 = task["train"][k]["input"]
        g1 = task["train"][k]["output"]
        allobjs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(g0))]
        by_cells = {frozenset(o.cells): o for o in allobjs}
        gid0, gid1 = pn.input_grid.node_id, pn.output_grid.node_id
        recolored = []
        for a, b, cat in _fg_correspondence(ag, gid0, gid1, g0, g1):
            def _t(p, cat=cat):
                v = cat.get(p)
                return v.get("type") if isinstance(v, dict) else v
            (g0cells, _), (_, g1col) = _obj_cc(idx["nodes"][a]), _obj_cc(idx["nodes"][b])
            if _t("coordinate") == "COMM" and _t("color") == "DIFF":
                o = by_cells.get(frozenset(tuple(sorted(map(tuple, g0cells)))))
                if o is not None:
                    recolored.append((o, g1col))
        pairs.append(Pair(allobjs, recolored, len(g0), len(g0[0])))
    return pairs


# ---------------------------------------------------------------------------
# 2. binding vocabulary — features (lookup) + relations (projection)
# ---------------------------------------------------------------------------
# feature fn signature: f(o, selection, pair) -> hashable value (or None)
def _rank(o, selection, key, order):
    rev = (order == "desc")
    ordered = sorted(selection, key=lambda x: (key(x), x.topleft), reverse=rev)
    # stable tie handling: re-sort ascending topleft after primary key
    ordered = sorted(selection, key=lambda x: (-key(x) if rev else key(x), x.topleft))
    return ordered.index(o)


# ordered by generality prior: relative rank & parity (structural, generalise well) →
# topology (holes/shape) → raw dimensions → raw size LAST (most memorisation-prone).
FEATURES = [
    ("rank(size,desc)", lambda o, s, p: _rank(o, s, lambda x: x.size, "desc")),
    ("rank(size,asc)",  lambda o, s, p: _rank(o, s, lambda x: x.size, "asc")),
    ("parity(width)",   lambda o, s, p: o.width % 2),
    ("parity(height)",  lambda o, s, p: o.height % 2),
    ("parity(size)",    lambda o, s, p: o.size % 2),
    ("holes",           lambda o, s, p: o.holes),
    ("shape_topo",      lambda o, s, p: o.shape_topo),
    ("shape",           lambda o, s, p: o.shape),
    ("width",           lambda o, s, p: o.width),
    ("height",          lambda o, s, p: o.height),
    ("bbox",            lambda o, s, p: (o.height, o.width)),
    ("size",            lambda o, s, p: o.size),
]

# relation fn signature: r(o, pair) -> colour (or None)
def _rel_adjacent_color(o, pair):
    cols = {q.color for q in pair.adjacency()[o] if q.color != o.color}
    return next(iter(cols)) if len(cols) == 1 else None


def _rel_nearest_diff_color(o, pair):
    cand = [q for q in pair.allobjs if q is not o and q.color != o.color]
    if not cand:
        return None
    def d(q):
        return (o.centroid[0] - q.centroid[0]) ** 2 + (o.centroid[1] - q.centroid[1]) ** 2
    best = min(cand, key=lambda q: (d(q), q.topleft))
    return best.color


def _rel_container_color(o, pair):
    """the object whose bbox strictly encloses o and is 4-adjacent (o sits in its hole)."""
    encl = [q for q in pair.adjacency()[o]
            if q.color != o.color and q.r0 <= o.r0 and q.c0 <= o.c0
            and q.r1 >= o.r1 and q.c1 >= o.c1 and q.size > o.size]
    cols = {q.color for q in encl}
    return next(iter(cols)) if len(cols) == 1 else None


RELATIONS = [
    ("adjacent_color", _rel_adjacent_color),
    ("container_color", _rel_container_color),
    ("nearest_diff_color", _rel_nearest_diff_color),
]


# ---------------------------------------------------------------------------
# 3. binding + active search
# ---------------------------------------------------------------------------
@dataclass
class Binding:
    kind: str                       # 'const' | 'lookup' | 'relation'
    name: str = ""                  # feature or relation name
    table: dict = field(default_factory=dict)   # lookup: value -> colour
    color: int = None               # const
    _relfn = None
    _featfn = None

    def resolve(self, o, selection, pair):
        if self.kind == "const":
            return self.color
        if self.kind == "lookup":
            return self.table.get(self._featfn(o, selection, pair))
        if self.kind == "relation":
            return self._relfn(o, pair)
        return None

    def describe(self):
        if self.kind == "const":
            return f"out_color = {self.color} (const)"
        if self.kind == "lookup":
            tbl = ", ".join(f"{k}->{v}" for k, v in sorted(self.table.items(), key=lambda kv: str(kv[0])))
            return f"out_color = table[{self.name}(o)]   table={{{tbl}}}"
        return f"out_color = color_of({self.name}(o))"

    def color_expr(self):
        if self.kind == "const":
            return str(self.color)
        if self.kind == "lookup":
            tbl = "{" + ", ".join(f"{k!r}: {v}" for k, v in sorted(self.table.items(), key=lambda kv: str(kv[0]))) + "}"
            return f"table[{self.name}(o)]   with table = {tbl}"
        return f"color_of({self.name}(o))     # o의 {self.name} 관계 대상의 색"


# ── selection predicates — WHICH objects get recoloured (searched, not assumed) ──
class Sel:
    def __init__(self, name, fn, expr):
        self.name, self.fn, self.expr = name, fn, expr


def _largest_of(pair, c):
    cs = [o for o in pair.allobjs if o.color == c]
    return max(cs, key=lambda o: (o.size, o.topleft)) if cs else None


def _enclosed(o, pair):
    return o.r0 > 0 and o.c0 > 0 and o.r1 < pair.H - 1 and o.c1 < pair.W - 1


def selection_candidates(c):
    return [
        Sel(f"color=={c}", lambda o, p, c=c: o.color == c, f"color_of(o) == {c}"),
        Sel(f"color=={c} ∧ ¬largest", lambda o, p, c=c: o.color == c and o is not _largest_of(p, c),
            f"color_of(o) == {c} and o is not argmax(size, {{o: color_of(o)=={c}}})"),
        Sel(f"color=={c} ∧ enclosed", lambda o, p, c=c: o.color == c and _enclosed(o, p),
            f"color_of(o) == {c} and not touches_border(o)"),
        Sel(f"color=={c} ∧ holes==0", lambda o, p, c=c: o.color == c and o.holes == 0,
            f"color_of(o) == {c} and holes(o) == 0"),
    ]


def _selection_color(pairs):
    cols = {o.color for p in pairs for (o, _oc) in p.recolored}
    return next(iter(cols)) if len(cols) == 1 else None


def _apply_solution(grid, sel, binding):
    allobjs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
    pair = Pair(allobjs, [], len(grid), len(grid[0]))
    chosen = [o for o in allobjs if sel.fn(o, pair)]
    out = [row[:] for row in grid]
    for o in chosen:
        nc = binding.resolve(o, chosen, pair)
        if nc is None:
            return None
        for (r, c) in o.cells:
            out[r][c] = nc
    return out


def _verify(task, sel, binding):
    """the honest gate: a candidate is accepted only if it reproduces EVERY train output
    when actually executed on the full grid (not merely 'consistent' on the recolor signal)."""
    for ex in task["train"]:
        if _apply_solution(ex["input"], sel, binding) != ex["output"]:
            return False
    return True


def _candidate_bindings(pairs, sel):
    """generate colour-binding candidates for a fixed selection: const, each relation
    projection, each feature lookup. Each yields (label, Binding)."""
    selected = [[o for o in p.allobjs if sel.fn(o, p)] for p in pairs]
    outmap = {id(o): oc for p in pairs for (o, oc) in p.recolored}
    # const
    outs = {oc for p in pairs for (o, oc) in p.recolored}
    yield ("const", Binding("const", "const", color=(next(iter(outs)) if len(outs) == 1 else None)))
    # relations
    for name, fn in RELATIONS:
        b = Binding("relation", name); b._relfn = fn
        yield (f"rel:{name}", b)
    # feature lookups — table learned from the recolour signal
    for name, fn in FEATURES:
        table, ok = {}, True
        for p, selp in zip(pairs, selected):
            for o in selp:
                if id(o) not in outmap:
                    continue
                v = fn(o, selp, p)
                if v in table and table[v] != outmap[id(o)]:
                    ok = False; break
                table[v] = outmap[id(o)]
            if not ok:
                break
        if ok and table:
            b = Binding("lookup", name, table=table); b._featfn = fn
            yield (f"feat:{name}", b)


def search_solution(task, pairs, sel_color):
    """ACTIVE search over (selection predicate × colour binding), each candidate GATED by
    execution-verification against all train grids. Returns (Sel, Binding, tried)."""
    tried = []
    recsets = [{o.cells for (o, _oc) in p.recolored} for p in pairs]
    for sc in selection_candidates(sel_color):
        selected = [{o.cells for o in p.allobjs if sc.fn(o, p)} for p in pairs]
        if any(sel != rec for sel, rec in zip(selected, recsets)):
            tried.append((f"sel:{sc.name}", "selected set ≠ recoloured set"))
            continue
        for label, b in _candidate_bindings(pairs, sc):
            if b.kind == "const" and b.color is None:
                tried.append((f"{sc.name} | const", "colours not constant")); continue
            if _verify(task, sc, b):
                return sc, b, tried
            tried.append((f"{sc.name} | {label}", "does not reproduce all train outputs"))
    return None, None, tried


def solution_program(sel, binding):
    return "\n".join([
        "# TASK.solution  (anti-unified over all train pairs)",
        f"sel = [o for o in objects_of(input_grid) if {sel.expr}]",
        "grid = input_grid",
        "for o in sel:",
        f"    out_color = {binding.color_expr()}",
        "    grid = apply_DSL(grid, coloring, o.coord, out_color)",
        "output_grid = grid",
    ])


@dataclass
class Result:
    tid: str
    ok: bool
    binding: Binding = None
    sel: Sel = None
    sel_color: int = None
    train_ok: list = field(default_factory=list)
    test_ok: bool = None
    tried: list = field(default_factory=list)
    note: str = ""


def abstract_task(tid, task):
    pairs = per_pair_objects(task)
    n_recolor = sum(len(p.recolored) for p in pairs)
    if n_recolor == 0:
        return Result(tid, False, note="no recolor objects — not an object-recolor task")
    sel_color = _selection_color(pairs)
    if sel_color is None:
        cols = sorted({o.color for p in pairs for (o, _oc) in p.recolored})
        return Result(tid, False, note=f"recoloured objects span multiple in_colors {cols} "
                                        "— selection not a single colour")
    sel, binding, tried = search_solution(task, pairs, sel_color)
    if binding is None:
        return Result(tid, False, sel_color=sel_color, tried=tried,
                      note="IMPASSE: no (selection × feature/relation binding) in the current "
                           "vocabulary reproduces all pairs (abstraction-gap)")
    train_ok = [_apply_solution(ex["input"], sel, binding) == ex["output"] for ex in task["train"]]
    test_ok = None
    if task.get("test") and "output" in task["test"][0]:
        test_ok = _apply_solution(task["test"][0]["input"], sel, binding) == task["test"][0]["output"]
    r = Result(tid, all(train_ok), binding=binding, sel=sel, sel_color=sel_color,
               train_ok=train_ok, test_ok=test_ok, tried=tried,
               note="task-general solution reproduces all train pairs")
    r.solution = solution_program(sel, binding)
    r.test_pred = _apply_solution(task["test"][0]["input"], sel, binding) if task.get("test") else None
    return r


if __name__ == "__main__":
    from arc.focus_solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    order = ["08ed6ac7", "845d6e51", "868de0fa", "009d5c81", "0ca9ddb6", "11852cab",
             "made000a", "made000b"]
    for tid in order:
        if tid not in tasks:
            continue
        r = abstract_task(tid, tasks[tid])
        mark = ("✅ SOLVE " if (r.ok and r.test_ok is not False)
                else ("⚠ OVERFIT" if r.ok else "·       "))
        print(f"\n{mark}  {tid}  (train={len(tasks[tid]['train'])})")
        for t, why in r.tried:
            print(f"     ✗ {t}: {why}")
        if r.binding:
            print(f"     ✓ selection [{r.sel.name}]  +  {r.binding.describe()}")
            print(f"   train_ok={r.train_ok}  test_ok={r.test_ok}")
        else:
            print(f"   {r.note}")
