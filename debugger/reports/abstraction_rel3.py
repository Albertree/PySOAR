"""Select by RELATIONAL-PROFILE MATCH, not by a hardcoded predicate or an explicit count
(user, 2026-07-13).

Objections addressed:
  - no `is_greater_than_all_siblings`: 'all/모두 큼' must EMERGE, not be a function.
  - no `greater_count == 3`: don't COUNT to a value; match the DISTRIBUTION of the relation.
  - the 'compare only same-colour' scope is a BIAS — discover it by search, don't hardcode.

Mechanism:
  profile(o | scope, prop) = the multiset of pairwise arithmetic relations of `prop` between
      o and the other objects in `scope`  (e.g. (' >',' >',' >')  or  ('<',' >',' >')).
  Two objects have the SAME relation (2nd-order COMM) iff their profiles are equal.
  The example's blue-turned object has some profile; it is COMM across the two pairs; at TEST
  we pick the object whose profile MATCHES it → blue. General rule = {profile → colour},
  learned from the examples (COMM across pairs), applied by profile match. No 'all', no count
  to a literal — only 'same distribution of the relation'. The comparison SCOPE (all objects
  vs same-colour group) and the PROPERTY are SEARCHED; the combo under which the profile→colour
  map is consistent across pairs AND reproduces the outputs is the discovered bias.
"""
from __future__ import annotations

from debugger.reports.abstraction import per_pair_objects, Obj
from arbor.solver import objects_of

# candidate comparison SCOPES (the 'compare only grey' bias is one of these — to be found)
SCOPES = {
    "all objects": lambda o, objs: [q for q in objs if q is not o],
    "same-colour group": lambda o, objs: [q for q in objs if q is not o and q.color == o.color],
}
# candidate numeric PROPERTIES to compare (native / coordinate-derived)
PROPS = {"area": lambda o: o.size, "bbox-h": lambda o: o.height, "bbox-w": lambda o: o.width}


def sign(a, b):
    return ">" if a > b else ("<" if a < b else "=")


def profile(o, objs, scope, prop):
    """relation DISTRIBUTION of o vs its scope on `prop` — a sorted multiset of signs.
    (order-independent 'pattern of the relation', not a count to a value.)"""
    sc = SCOPES[scope](o, objs)
    return tuple(sorted(sign(PROPS[prop](o), PROPS[prop](q)) for q in sc))


def _pair_map(p, sel_color, scope, prop):
    outmap = {id(o): oc for (o, oc) in p.recolored}
    return {profile(o, p.allobjs, scope, prop): outmap[id(o)]
            for o in p.allobjs if o.color == sel_color and id(o) in outmap}


def learn_map(pairs, sel_color, scope, prop):
    """{profile → colour} from the recoloured objects. Accept ONLY if the profile→colour map
    is IDENTICAL across pairs — i.e. the relation DISTRIBUTION itself is COMM across pairs
    (2nd-order structure mapping), not a per-pair-distinct set that merely happens to be a
    consistent function. This is what rejects the 'all objects' scope (its profiles differ
    per pair, being cardinality-dependent) and discovers the same-colour bias."""
    maps = [_pair_map(p, sel_color, scope, prop) for p in pairs if p.recolored]
    if not maps:
        return None
    if any(m != maps[0] for m in maps):        # profiles NOT COMM across pairs
        return None
    return maps[0] or None


def apply_map(grid, sel_color, scope, prop, m):
    objs = [Obj(j, col, cells) for j, (cells, col) in enumerate(objects_of(grid))]
    out = [row[:] for row in grid]
    for o in objs:
        if o.color != sel_color:
            continue
        c = m.get(profile(o, objs, scope, prop))
        if c is None:
            return None
        for (r, cc) in o.cells:
            out[r][cc] = c
    return out


def discover(task):
    """search (scope × property); accept the combo whose profile→colour map is COMM across
    pairs AND reproduces every train output on execution. Returns dict or None + the log."""
    pairs = per_pair_objects(task)
    if not any(p.recolored for p in pairs):
        return None, [("—", "no recolor objects")], None
    sel = {o.color for p in pairs for (o, _oc) in p.recolored}
    if len(sel) != 1:
        return None, [("—", f"selected span colours {sorted(sel)}")], None
    sel_color = next(iter(sel))
    log = []
    for scope in SCOPES:
        for prop in PROPS:
            m = learn_map(pairs, sel_color, scope, prop)
            if m is None:
                log.append((f"{scope} · {prop}", "프로파일이 pair간 COMM 아님(분포 다름) 또는 함수 아님")); continue
            if all(apply_map(ex["input"], sel_color, scope, prop, m) == ex["output"]
                   for ex in task["train"]):
                return {"scope": scope, "prop": prop, "map": m, "sel_color": sel_color,
                        "pairs": pairs}, log, sel_color
            log.append((f"{scope} · {prop}", "map consistent but does not reproduce outputs"))
    return None, log, sel_color


if __name__ == "__main__":
    from arbor.solver import _load_survey, SURVEY_AGI
    tasks = dict(_load_survey(agi_ids=SURVEY_AGI))
    for tid in ("08ed6ac7", "845d6e51", "868de0fa"):
        task = tasks[tid]
        sol, log, sc = discover(task)
        print("\n" + "=" * 70 + f"\n{tid}\n" + "=" * 70)
        print("  scope × property 탐색 (bias 발견):")
        for combo, why in log:
            print(f"     ✗ {combo}: {why}")
        if sol is None:
            print("     → 도출 실패 (honest abstraction-gap)"); continue
        print(f"     ✓ {sol['scope']} · {sol['prop']}  — 이 scope/property 에서 프로파일→색이 COMM+재현")
        print(f"\n  프로파일(관계 분포) → 색  맵 (pair간 COMM):")
        for pf, c in sorted(sol["map"].items(), key=lambda kv: kv[0].count(">"), reverse=True):
            print(f"     {pf}  → color {c}")
        # show each pair's objects with their profile (no count exposed — just the pattern)
        for k, p in enumerate(sol["pairs"]):
            outmap = {id(o): oc for (o, oc) in p.recolored}
            objs = [o for o in p.allobjs if o.color == sol["sel_color"] and id(o) in outmap]
            print(f"  pair {k}: " + " | ".join(
                f"{profile(o, p.allobjs, sol['scope'], sol['prop'])}→{outmap[id(o)]}" for o in objs))
        # selection reason (profile match, no 'all', no count)
        blue = min(sol["map"], key=lambda pf: pf.count("<"))   # the profile of the blue-turned obj
        print(f"\n  선택 근거: test input 의 각 {sol['sel_color']}색 객체를 {sol['scope']}과 {sol['prop']} 로 비교해")
        print(f"            그 관계 분포가 예시의 파란 객체 프로파일 {blue} 와 COMM(같음)인 객체를 파랑으로.")
        print("            (— 'all' 술어도, 'count==N' 도 없음. 분포 일치로만 선택.)")
        # verify on test
        te = apply_map(task["test"][0]["input"], sol["sel_color"], sol["scope"], sol["prop"], sol["map"]) \
            == task["test"][0].get("output")
        tr = [apply_map(ex["input"], sol["sel_color"], sol["scope"], sol["prop"], sol["map"]) == ex["output"]
              for ex in task["train"]]
        print(f"  train_ok={tr}  test_ok={te}")
