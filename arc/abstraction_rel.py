"""Compare-driven abstraction (prototype) — derive the selection/assignment REASON from
COMM/DIFF only, never from hand-coded concepts (harness §2-2, §4-2, §1-2).

The initial agent has ONE primitive: compare(a, b) → COMM/DIFF per property. From that it
may derive, generically:
  - number DIFF  → order (greater / less)          ["숫자는 다르다 아래 크다/작다"]
  - counting typed relations → a relational profile ["outgoing longer_than edge 3개" = §4-2]
No `holes`, `shape_topo`, `parity`, `argmax`, `rank` concept is supplied. The *scope* of
comparison (which siblings) is itself derived by a categorical COMM grouping (e.g. same
colour), not assumed.

Demonstration target: 08ed6ac7. "가장 긴 회색" is NOT given — each recoloured object is
compared to its same-colour siblings; its position in the size-order is COUNTED (# it
exceeds); objects that map to the SAME output colour are shown to SHARE that count across
pairs (structure mapping). That shared relational profile IS the derived reason.

Honesty: parity-type rules (868de0fa) do NOT fall out of compare+order+count — they need a
concept the agent must INVENT. Those stay an honest abstraction-gap here (that is correct).
"""
from __future__ import annotations

from arc.abstraction import per_pair_objects, Obj, Pair
from arc.focus_solver import objects_of


# ── the only primitives: compare + generic refinements ─────────────────────
def cmp_cat(a_val, b_val):
    """categorical compare → COMM/DIFF (colour, shape-as-cellset, …)."""
    return "COMM" if a_val == b_val else "DIFF"


def cmp_num(a_val, b_val):
    """numeric compare → COMM, or DIFF refined into an order sign (generic to any number)."""
    if a_val == b_val:
        return "COMM", 0
    return "DIFF", (1 if a_val > b_val else -1)


# native ARCKG-ish object properties the agent may read (NOT invented concepts):
#   colour (categorical), size=cell-count (numeric), shape=cellset (categorical), coord.
def group_by_comm(objs, prop):
    """partition objs into COMM-groups on a categorical property (derived scope)."""
    groups = {}
    for o in objs:
        groups.setdefault(prop(o), []).append(o)
    return groups


def order_count(o, siblings, num):
    """relational profile component: how many siblings this object EXCEEDS on a numeric
    property — pure count of compare(DIFF, order=+). '가장 큰' = exceeds all (count = n-1);
    'nothing exceeds it' = 0 incoming. No 'rank'/'max' concept used, only counting."""
    out_gt = sum(1 for s in siblings if s is not o and cmp_num(num(o), num(s))[1] > 0)
    in_gt = sum(1 for s in siblings if s is not o and cmp_num(num(o), num(s))[1] < 0)
    return out_gt, in_gt


PROP = {"color": lambda o: o.color, "size": lambda o: o.size,
        "shape": lambda o: o.shape}


def derive_reason(task):
    """try to explain each recoloured object's OUTPUT colour by a relational profile taken
    over a COMM-derived sibling scope + a numeric order-count. Search over (grouping prop,
    ordering prop); accept the profile that is COMM (consistent) across all pairs. Returns
    a dict with the derived scope/profile + the table, or None (honest abstraction-gap)."""
    pairs = per_pair_objects(task)
    if not any(p.recolored for p in pairs):
        return None
    # the selected objects share a colour (compare COMM); that colour-group is the scope.
    sel_color = {o.color for p in pairs for (o, _oc) in p.recolored}
    if len(sel_color) != 1:
        return None
    c = next(iter(sel_color))

    # candidate profiles: order-count on each numeric property, over the same-colour group.
    for num_name in ("size",):                       # extendable: width/height/area…
        num = {"size": lambda o: o.size}[num_name]
        table, per_pair_profiles, ok = {}, [], True
        for p in pairs:
            group = [o for o in p.allobjs if o.color == c]     # scope by colour-COMM
            prof = {}
            for (o, oc) in p.recolored:
                out_gt, in_gt = order_count(o, group, num)
                prof[(o.size, out_gt, in_gt)] = oc
                key = out_gt                                    # profile = "# siblings exceeded"
                if key in table and table[key] != oc:
                    ok = False
                table[key] = oc
            per_pair_profiles.append(prof)
        if ok and table:
            return {"scope": f"objects COMM in colour (= {c})", "order_prop": num_name,
                    "profile": "out_gt = #{siblings this object is larger than}",
                    "table": table, "per_pair": per_pair_profiles, "sel_color": c}
    return None


def apply_reason(grid, reason):
    """apply the compare-derived reason to a fresh grid: group by colour-COMM, count
    order-exceed among siblings, look up the derived table. (No concept injected.)"""
    objs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
    c = reason["sel_color"]
    group = [o for o in objs if o.color == c]
    out = [row[:] for row in grid]
    for o in group:
        out_gt = sum(1 for s in group if s is not o and s.size < o.size)
        col = reason["table"].get(out_gt)
        if col is None:
            return None
        for (r, cc) in o.cells:
            out[r][cc] = col
    return out


if __name__ == "__main__":
    from arc.focus_solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    for tid in ("08ed6ac7", "868de0fa"):
        task = tasks[tid]
        print("\n" + "=" * 64 + f"\n{tid}\n" + "=" * 64)
        reason = derive_reason(task)
        if reason is None:
            print("  no compare-derived reason (honest abstraction-gap — needs an invented concept)")
            continue
        print(f"  derived scope   : {reason['scope']}")
        print(f"  derived profile : {reason['profile']}  (order on {reason['order_prop']})")
        print(f"  → 관계프로파일 → 출력색 표: {reason['table']}")
        for k, prof in enumerate(reason["per_pair"]):
            print(f"    pair {k}:  " + ";  ".join(
                f"(size {sz}, exceeds {og}, exceeded-by {ig}) → color {oc}"
                for (sz, og, ig), oc in sorted(prof.items(), key=lambda kv: -kv[0][1])))
        # verify by execution on train + test (no concept used in apply either)
        tr = [apply_reason(ex["input"], reason) == ex["output"] for ex in task["train"]]
        te = None
        if task.get("test") and "output" in task["test"][0]:
            te = apply_reason(task["test"][0]["input"], reason) == task["test"][0]["output"]
        print(f"  train_ok={tr}  test_ok={te}   →  "
              + ("✅ 선택이유가 compare 만으로 도출·검증됨" if all(tr) and te else "부분/실패"))
