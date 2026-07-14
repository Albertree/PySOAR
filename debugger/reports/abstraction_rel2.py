"""'largest' WITHOUT a largest()/argmax()/rank() concept — derived from COMM/DIFF + a deep
analysis of the DIFF into an arithmetic order (user, 2026-07-13).

Mechanism (08ed6ac7):
  1. object mapping (compare): a grey object → blue, only COLOR changed (pos/size/shape COMM).
  2. selection at TEST from the input grid alone: compare each grey object to its same-colour
     siblings. The one that maps to blue has the relational profile
         ∀ same-colour sibling s :  compare(area) = DIFF  ∧  deep(area) = '>'
     i.e. its area is DIFF from every grey sibling AND arithmetically GREATER in every case.
  3. that profile is COMM across the two training pairs → it is the selection reason.
  4. at test: pick the grey object whose area is DIFF-and-'>' vs all other greys → blue.

No largest/argmax/rank is implemented. Only: compare→COMM/DIFF, and number-DIFF refined to
the arithmetic relation '>'/'<'. The general 08ed rule (all greys recoloured by order) is the
same engine: colour is fixed by HOW MANY grey siblings the object is arithmetically '>' than.
"""
from __future__ import annotations

from debugger.reports.abstraction import per_pair_objects, Obj, Pair
from arbor.solver import objects_of


# ── the only primitives ─────────────────────────────────────────────────────
def compare_area(a, b):
    """native compare on the numeric property 'area', with the DIFF deep-analysed into an
    arithmetic order. Returns ('COMM','=') or ('DIFF','>') / ('DIFF','<')."""
    if a.size == b.size:
        return ("COMM", "=")
    return ("DIFF", ">" if a.size > b.size else "<")


def same_color_siblings(o, objs):
    """membership + colour-COMM scope: objects whose colour is COMM with o (excluding o)."""
    return [q for q in objs if q is not o and q.color == o.color]


def area_profile(o, objs):
    """relational profile of o vs its same-colour siblings: the multiset of (COMM/DIFF, order)."""
    return [compare_area(o, s) for s in same_color_siblings(o, objs)]


def is_greater_than_all_siblings(o, objs):
    """'가장 큼' effect: area DIFF from every same-colour sibling AND '>' in every comparison.
    No max/argmax — just: all pairwise area-compares are DIFF with arithmetic '>'."""
    prof = area_profile(o, objs)
    return len(prof) > 0 and all(r == ("DIFF", ">") for r in prof)


def greater_count(o, objs):
    """HOW MANY same-colour siblings o is arithmetically '>' than (the generalisation of the
    'bigger-than-all' profile to every ordinal position). Derived only from compare '>'."""
    return sum(1 for r in area_profile(o, objs) if r == ("DIFF", ">"))


# ── demonstrate on 08ed6ac7 ─────────────────────────────────────────────────
def demo(task, tid):
    pairs = per_pair_objects(task)
    sel_color = next(iter({o.color for p in pairs for (o, _oc) in p.recolored}))
    print("=" * 72 + f"\n{tid}   (selected colour by COMM = {sel_color})\n" + "=" * 72)

    # (1) the 'bigger-than-all-greys' selection profile, and the colour it maps to, per pair
    blue_profiles = []
    for k, p in enumerate(pairs):
        outmap = {id(o): oc for (o, oc) in p.recolored}
        greys = [o for o in p.allobjs if o.color == sel_color]
        print(f"\n pair {k}: {len(greys)} grey objects (area = # cells)")
        for o in sorted(greys, key=lambda o: -o.size):
            prof = area_profile(o, p.allobjs)
            tag = "  ← DIFF+'>' vs ALL siblings (bigger-than-all)" if is_greater_than_all_siblings(o, p.allobjs) else ""
            oc = outmap.get(id(o))
            print(f"    area {o.size:2d}  vs siblings {prof}  → color {oc}{tag}")
        # which object is 'bigger than all', and what colour does it get?
        big = next((o for o in greys if is_greater_than_all_siblings(o, p.allobjs)), None)
        blue_profiles.append(outmap.get(id(big)) if big else None)
    print(f"\n  selection profile '∀ grey sibling: area DIFF ∧ >' maps to colour {blue_profiles} "
          f"— {'COMM across pairs ✓' if len(set(blue_profiles)) == 1 else 'not COMM ✗'}")
    print("  → 선택 근거: color(o) COMM {c} ∧ (∀ s: color(s) COMM {c} → area(o) DIFF area(s) ∧ area(o) > area(s))"
          .replace("{c}", str(sel_color)))

    # (2) the full task rule = colour fixed by greater_count (same engine, every ordinal)
    table = {}
    ok = True
    for p in pairs:
        outmap = {id(o): oc for (o, oc) in p.recolored}
        for (o, oc) in p.recolored:
            gc = greater_count(o, p.allobjs)
            if gc in table and table[gc] != oc:
                ok = False
            table[gc] = oc
    print(f"\n  general rule: color = table[ #{{grey siblings o is '>' than}} ] = {table}"
          f"  ({'COMM across pairs' if ok else 'inconsistent'})")

    # (3) apply to TEST input alone (no answer peeked for selection)
    def apply(grid):
        objs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
        out = [row[:] for row in grid]
        for o in objs:
            if o.color != sel_color:
                continue
            col = table.get(greater_count(o, objs))
            if col is None:
                return None
            for (r, c) in o.cells:
                out[r][c] = col
        return out

    tr = [apply(ex["input"]) == ex["output"] for ex in task["train"]]
    te = None
    if task.get("test") and "output" in task["test"][0]:
        te = apply(task["test"][0]["input"]) == task["test"][0]["output"]
    # which grey does the test pick as 'bigger-than-all' → blue?
    tobjs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(task["test"][0]["input"]))]
    tbig = next((o for o in tobjs if o.color == sel_color and is_greater_than_all_siblings(o, tobjs)), None)
    print(f"\n  TEST: grey that is '>' than all others = area {tbig.size if tbig else None} "
          f"→ color {table.get(greater_count(tbig, tobjs)) if tbig else None}")
    print(f"  train_ok={tr}  test_ok={te}   →  "
          + ("✅ largest 없이 COMM/DIFF+arithmetic '>' 만으로 선택·풀이" if all(tr) and te else "부분/실패"))


if __name__ == "__main__":
    from arbor.solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    demo(tasks["08ed6ac7"], "08ed6ac7")
