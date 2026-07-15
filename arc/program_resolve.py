# -*- coding: utf-8 -*-
"""
program_resolve -- PROTOTYPE (2026-07-13, seokki-windows). anti-unify 가 남긴 **변수**(per-pair
DIFF 슬롯)를 **object 속성/관계의 COMM/DIFF** 로 해소해, 스키마를 test input 에서 실행 가능하게.

§1-1·§1-5 준수 — largest/move/around 같은 **새 concept DSL·이름붙인 관계를 만들지 않는다.** 선택
근거는 **ARCKG compare 의 COMM/DIFF**(속성의 같음/다름)로 *논리식*으로 표현한다:
  · object 선택 = 각 object 를 나머지와 **비교**(ARCKG `_compare_dicts`)해 속성별 COMM/DIFF 를 얻고,
    "속성 P 가 나머지 전부와 **DIFF**(=고유)" 또는 "P 가 나머지 전부보다 **greater**(=극단)" 처럼
    **COMM/DIFF/관계 위의 논리 술어**가 pair 간 일관되게 그 object 를 고르는지 **탐색·검증**한다.
    어떤 P·어떤 술어인지는 탐색(시도·기각이 남는다). 이름붙인 새 관계 없음 — 술어는 COMM/DIFF 그 자체.
  · 좌표 선택 = 목표좌표를 {grid H/W, object h/w, **object 위치 r0/c0**, 0,1} 조합식으로 탐색(§1-3).
못 찾으면 정직하게 impasse.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root

import arc.dsl  # noqa: F401,E402  (ARC-solver 를 sys.path 에 올린다)
from arc.select_solver import fg_objects   # noqa: E402  (predefined 전경 object 추출)
from ARCKG.comparison import _compare_dicts  # noqa: E402  (ARCKG COMM/DIFF 엔진)

NUM = {                                     # 수치 property (greater 관계용)
    "area":   lambda o: o["area"],
    "height": lambda o: max(o["rows"]) - min(o["rows"]) + 1,
    "width":  lambda o: max(o["cols"]) - min(o["cols"]) + 1,
}
# 선택 술어를 세울 속성들 (COMM/DIFF 로 비교). shape 는 정규화 상대좌표.
PROPS = ["color", "shape", "area", "height", "width"]


def _objs(grid, tag="G0"):
    return fg_objects(grid, tag)


def _cset(o):
    return frozenset(tuple(c) for c in o["cells"])


def _r0c0hw(o):
    rs = [c[0] for c in o["cells"]]; cs = [c[1] for c in o["cells"]]
    r0, c0 = min(rs), min(cs)
    return r0, c0, max(rs) - r0 + 1, max(cs) - c0 + 1


def _oprops(o):
    """object 의 비교용 속성 dict (ARCKG 8속성 중 이 프로토타입이 쓰는 것)."""
    r0, c0, h, w = _r0c0hw(o)
    return {"color": o["color"], "area": o["area"], "height": h, "width": w,
            "shape": sorted([c[0] - r0, c[1] - c0] for c in o["cells"])}


def commdiff(a, b):
    """두 object 의 **속성별 COMM/DIFF** (ARCKG `_compare_dicts`). {prop: 'COMM'|'DIFF'}."""
    cat = _compare_dicts(_oprops(a), _oprops(b)).get("category", {})
    return {k: v["type"] for k, v in cat.items()}


# --- compare-signature: object 를 그룹과 compare 한 결과의 집합 (원시 조합, 자연어 없음) --------
def _sig(o, group, P, key):
    """O 를 group 의 각 O' 와 compare → property P 의 (COMM/DIFF, arithmetic 부호) 결과 집합."""
    out = []
    for x in group:
        if x is o:
            continue
        if commdiff(o, x).get(P) == "COMM":
            out.append((P, "COMM"))
        else:
            out.append((P, "DIFF", ">" if key(o) > key(x) else "<"))
    return tuple(sorted(out))


def _grp_color(o, objs):
    return [x for x in objs if commdiff(o, x).get("color") == "COMM"]


_SIG_GROUPS = [("color=COMM", _grp_color), ("all", lambda o, objs: list(objs))]


def sig_str(S):
    return " ".join(f"{s[0]}:{s[1]}{s[2] if len(s) > 2 else ''}" for s in S) or "∅(그룹내 유일)"


def _pick_by_sig(P, key, gpred, S):
    """어떤 grid 에서든 signature 가 S 인 (그룹내 유일) object 를 고르는 일반 picker."""
    def f(objs):
        m = [o for o in objs if _sig(o, gpred(o, objs), P, key) == S]
        return m[0] if len(m) == 1 else None
    return f


# --- 선택 술어(picker): COMM/DIFF·관계 위의 논리식. 이름붙인 새 관계 아님 ----------
def _pick_unique(P):
    """"속성 P 가 나머지 전부와 DIFF" 인 유일 object (= P 가 고유). COMM/DIFF 로 판정."""
    def f(objs):
        chosen = [o for o in objs
                  if all(commdiff(o, o2).get(P) == "DIFF" for o2 in objs if o2 is not o)]
        return chosen[0] if len(chosen) == 1 else None
    return f


def _pick_extremum(P, dirn):
    """"P 가 나머지 전부보다 greater(max)/less(min)" 인 유일 object. 쌍끼리 비교로."""
    key = NUM[P]
    def f(objs):
        score = {id(o): sum(1 for b in objs if b is not o and key(o) > key(b)) for o in objs}
        target = (len(objs) - 1) if dirn == "max" else 0
        win = [o for o in objs if score[id(o)] == target]
        return win[0] if len(win) == 1 else None
    return f


def _bases():
    """선택 후보 술어들 — 전부 COMM/DIFF(고유) 또는 greater 관계 위의 논리식. 이름붙인 개념 없음."""
    bs = [("유일 object (선택 여지 없음)", lambda objs: objs[0] if len(objs) == 1 else None)]
    for P in PROPS:                                   # "P 가 남들과 DIFF (고유)"
        bs.append((f"O : {P}(O) ≠ 나머지 전부 (COMM/DIFF 로 {P} 고유)", _pick_unique(P)))
    for P in NUM:                                     # "P 가 남들보다 greater/less"
        bs.append((f"O : {P}(O) > 나머지 전부 (관계 {P} 최대)", _pick_extremum(P, "max")))
        bs.append((f"O : {P}(O) < 나머지 전부 (관계 {P} 최소)", _pick_extremum(P, "min")))
    return bs


def _consistent_bases(train, check):
    """각 술어를 pair 간 검증. train 에 **일관한 술어 전부** + 시도목록 반환 (첫째만이 아님 —
    여럿이 일관하면 underdetermined 일 수 있으므로 test 에서 일치하는지 뒤에서 검증)."""
    tried, good = [], []
    for desc, picker in _bases():
        ok = True
        for i, p in enumerate(train):
            objs = _objs(p["input"], f"P{i}")
            pk = picker(objs)
            if pk is None or not check(pk, objs, i):
                ok = False
                break
        tried.append((desc, ok))
        if ok:
            good.append((desc, picker))
    return good, tried


# --- 좌표 표현식 탐색 (grid H/W · object h/w · object 위치 r0/c0) -----------------
_ATOMS = ["0", "1", "H", "W", "h", "w", "r0", "c0"]


def _aval(a, ctx):
    return {"0": 0, "1": 1}.get(a, ctx.get(a))


def _coord_candidates():
    cands = [(a, (lambda ctx, a=a: _aval(a, ctx))) for a in _ATOMS]
    for a in _ATOMS:
        for b in _ATOMS:
            cands.append((f"{a}-{b}", lambda ctx, a=a, b=b: _aval(a, ctx) - _aval(b, ctx)))
            cands.append((f"{a}+{b}", lambda ctx, a=a, b=b: _aval(a, ctx) + _aval(b, ctx)))
    return cands


def _fit_axis(samples, axis):
    """samples: [(ctx, tr, tc)]. train 에 일관한 식 **전부** (underdetermination 판정용)."""
    return [(name, fn) for name, fn in _coord_candidates()
            if all(fn(ctx) == (tr if axis == 0 else tc) for (ctx, tr, tc) in samples)]


def _norm_shape(cells):
    rs = [c[0] for c in cells]; cs = [c[1] for c in cells]
    r0, c0 = min(rs), min(cs)
    return frozenset((r - r0, c - c0) for (r, c) in cells)


# --- 변수 해소 ---------------------------------------------------------------
def _ctx(o, grid):
    r0, c0, h, w = _r0c0hw(o)
    return {"H": len(grid), "W": len(grid[0]), "h": h, "w": w, "r0": r0, "c0": c0}


def _resolve_color(cvals, train, test_in):
    good, tried = _consistent_bases(train, lambda pk, objs, i: pk["color"] == cvals[i])
    if not good:
        return {"resolved": False, "desc": "색을 비교로 해소 못함 (impasse)", "tried": tried, "eval": None}
    tobjs = _objs(test_in)
    picks = [picker(tobjs) for _, picker in good]
    vals = {o["color"] for o in picks if o}                    # test 에서 각 근거가 고른 색
    if None in [p for p in picks] and not vals:
        return {"resolved": False, "desc": "test 에서 object 선택 불가 (impasse)", "tried": tried, "eval": None}
    if len(vals) != 1:                                          # 근거들이 test 에서 불일치 = underdetermined
        return {"resolved": False, "desc": f"underdetermined — {len(good)}개 근거가 test 에서 색 불일치",
                "tried": tried, "eval": None}
    desc = good[0][0]
    return {"resolved": True, "desc": f"색 = ({desc}) 의 color", "tried": tried,
            "eval": lambda g: (lambda o: o["color"] if o else None)(good[0][1](_objs(g)))}


def _resolve_cells(cellvals, train, test_in):
    want = [frozenset(tuple(c) for c in cv) for cv in cellvals]
    # (a) in-place: 변수 셀 = 어떤 object 의 셀. 그 object 를 **compare-signature** 로 특정한다.
    tgt, tried = [], []
    for i, p in enumerate(train):
        objs = _objs(p["input"], f"P{i}")
        m = [o for o in objs if _cset(o) == want[i]]
        if len(m) == 1:
            tgt.append((objs, m[0]))
        else:
            tgt = None
            break
    if tgt:
        for P, key in NUM.items():
            for gname, gpred in _SIG_GROUPS:
                sigs = [_sig(o, gpred(o, objs), P, key) for objs, o in tgt]
                consistent = len(set(sigs)) == 1
                unique = consistent and all(
                    sum(1 for x in objs if _sig(x, gpred(x, objs), P, key) == sigs[0]) == 1
                    for objs, o in tgt)
                tried.append((f"compare on {P} within {gname}: "
                              f"sig=({sig_str(sigs[0])})" if consistent else f"{P} within {gname}: pair 간 sig 불일치",
                              unique))
                if not unique:
                    continue
                S = sigs[0]
                picker = _pick_by_sig(P, key, gpred, S)
                if picker(_objs(test_in)) is None:              # test 에서 유일 매칭 안 되면 다음
                    continue
                return {"resolved": True,
                        "desc": f"compare-signature on {P} within {gname} = ({sig_str(S)}) 인 object 의 셀",
                        "tried": tried,
                        "eval": (lambda pk=picker: lambda g:
                                 (lambda o: [list(c) for c in o["cells"]] if o else None)(pk(_objs(g))))()}
    # (b) translated: shape 일치 object 선택 → 위치는 좌표식 탐색(위치 atom 포함)
    sgood, stried = _consistent_bases(
        train, lambda pk, objs, i: _norm_shape(pk["cells"]) == _norm_shape([tuple(c) for c in cellvals[i]]))
    tried = tried + [("── 이동(translated)로 재시도 ──", bool(sgood))] + stried
    if not sgood:
        return {"resolved": False, "desc": "이동 대응 object 선택 근거 못 찾음 (impasse)", "tried": tried, "eval": None}
    sdesc, spicker = sgood[0]
    samples = []
    for i, p in enumerate(train):
        pk = spicker(_objs(p["input"], f"P{i}"))
        tr = min(c[0] for c in cellvals[i]); tc = min(c[1] for c in cellvals[i])
        samples.append((_ctx(pk, p["input"]), tr, tc))
    row_fits, col_fits = _fit_axis(samples, 0), _fit_axis(samples, 1)
    tpk = spicker(_objs(test_in))
    if tpk is None or not row_fits or not col_fits:
        tried.append(("좌표식/ test 선택", False))
        return {"resolved": False, "desc": "이동 좌표식 없음 또는 test 선택 불가 (impasse)", "tried": tried, "eval": None}
    tctx = _ctx(tpk, test_in)
    rvals = {fn(tctx) for _, fn in row_fits}; cvals = {fn(tctx) for _, fn in col_fits}
    tried.append((f"row 후보 {len(row_fits)}개 → test 값 {sorted(rvals)}", len(rvals) == 1))
    tried.append((f"col 후보 {len(col_fits)}개 → test 값 {sorted(cvals)}", len(cvals) == 1))
    if len(rvals) != 1 or len(cvals) != 1:                      # 후보들이 test 에서 불일치 = underdetermined
        return {"resolved": False, "desc": "underdetermined — 좌표식이 train 2쌍으로 미결정(후보 test 불일치)",
                "tried": tried, "eval": None}
    rname, rfn = row_fits[0]; cname, cfn = col_fits[0]

    def _ev(g, spicker=spicker, rfn=rfn, cfn=cfn):
        pk = spicker(_objs(g))
        if pk is None:
            return None
        r0, c0, _h, _w = _r0c0hw(pk)
        ctx = _ctx(pk, g)
        dr, dc = rfn(ctx) - r0, cfn(ctx) - c0
        return [[c[0] + dr, c[1] + dc] for c in pk["cells"]]
    return {"resolved": True, "desc": f"({sdesc}) 를 (row={rname}, col={cname}) 로 이동", "tried": tried, "eval": _ev}


def resolve_variable(vals, train, test_in):
    raw = [v["lit"] if isinstance(v, dict) and "lit" in v else v for v in vals]
    if all(isinstance(x, int) for x in raw):
        return _resolve_color(raw, train, test_in)
    if all(isinstance(x, list) for x in raw):
        return _resolve_cells(raw, train, test_in)
    return {"resolved": False, "desc": "미지원 변수 타입", "tried": [], "eval": None}


# --- 스키마를 test input 에서 실행 -------------------------------------------
def eval_term(term, test_input, resolutions):
    from procedural_memory.DSL.make_grid import make_grid
    if "var" in term:
        r = resolutions.get(term["var"])
        return r["eval"](test_input) if (r and r["eval"]) else None
    if "lit" in term:
        return term["lit"]
    if term["op"] == "input":
        return [row[:] for row in test_input]
    args = [eval_term(a, test_input, resolutions) for a in term["args"]]
    if any(a is None for a in args):
        return None
    if term["op"] == "make_grid":
        return make_grid(*args)
    if term["op"] == "coloring":
        return arc.dsl.coloring(*args)
    return None


def resolve_schema(schema, subst, train, test_input):
    """모든 변수를 해소 시도 → 전부 되면 test 실행. 예외는 정직한 impasse."""
    resolutions = {}
    for v, vals in subst.items():
        try:
            resolutions[v] = resolve_variable(vals, train, test_input)
        except Exception as e:                                   # noqa: BLE001
            resolutions[v] = {"resolved": False, "tried": [],
                              "desc": f"해소 중 예외: {type(e).__name__}", "eval": None}
    all_ok = all(r["resolved"] for r in resolutions.values()) if resolutions else True
    out = None
    if all_ok:
        try:
            out = eval_term(schema, test_input, resolutions)
        except Exception:                                        # noqa: BLE001
            out = None
    return {"resolutions": resolutions, "all_resolved": all_ok, "test_output": out}
