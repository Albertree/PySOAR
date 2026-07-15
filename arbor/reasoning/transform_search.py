# -*- coding: utf-8 -*-
"""transform_search — COMM/DIFF 기반 effect 도출 + DSL 후보 fan-out + arg resolve/verify.
DSL 은 finder 가 아니라 search 가 열거하는 어휘. propose=effect 일치, arg=즉시|탐색, 검증=train."""
from collections import Counter
from procedural_memory.dsl.effect import effect, matches
import procedural_memory.dsl as _dsl            # SPECS 채우는 import 부작용
from procedural_memory.dsl.registry import SPECS, body
from arbor.perception.arckg.hodel import find_all_objects


def _dims(g): return (len(g), len(g[0]))
def _palette(g): return frozenset(v for r in g for v in r)
def _multiset(g): return Counter(v for r in g for v in r)


def derive_required_effect(train):
    """generic 관찰만으로 required verb 집합을 낸다(문제특이 값·1:1 매핑 금지). 한 관찰이 후보 *집합*을 냄."""
    verbs = set()
    d = [(_dims(e["input"]), _dims(e["output"])) for e in train]
    same_dims = all(i == o for i, o in d)
    swapped = all((o[0], o[1]) == (i[1], i[0]) for i, o in d)
    changed = any(e["input"] != e["output"] for e in train)
    pal_keep = all(_palette(e["input"]) == _palette(e["output"]) for e in train)
    ms_keep = all(_multiset(e["input"]) == _multiset(e["output"]) for e in train)

    if same_dims and changed:
        if ms_keep:
            verbs |= {"rotate", "reflect", "translate"}   # 픽셀 보존 → 재배치류
        if not pal_keep:
            verbs.add("recolor")                          # 팔레트 변화 → 재채색
    if swapped and not same_dims:
        verbs |= {"rotate", "reflect"}
    # 확대/축소 (정수배)
    def ratio(i, o, ax):
        a, b = i[ax], o[ax]
        return ("up", b // a) if b >= a and a and b % a == 0 else \
               ("down", a // b) if a and b and a % b == 0 else (None, None)
    if all(ratio(i, o, 0)[0] == "up" and ratio(i, o, 1)[0] == "up" for i, o in d) and not same_dims:
        verbs.add("upscale")
    if all(ratio(i, o, 0)[0] == "down" and ratio(i, o, 1)[0] == "down" for i, o in d) and not same_dims:
        verbs |= {"downscale", "crop"}
    return [effect(v, "grid") for v in sorted(verbs)]


def candidate_transforms(required):
    return [n for n, s in SPECS.items()
            if s["kind"] == "transformation" and s["effect"]
            and any(matches(r, s["effect"]) for r in required)]


def _recolor_map(train):
    """전 train pair 셀단위 입력색→출력색 전역맵(크기 COMM 만). 비함수면 None. ①relation 즉시 arg."""
    if any(_dims(e["input"]) != _dims(e["output"]) for e in train):
        return None
    mp = {}
    for e in train:
        i, o = e["input"], e["output"]
        for r in range(len(i)):
            for c in range(len(i[0])):
                a, b = i[r][c], o[r][c]
                if a in mp and mp[a] != b:
                    return None
                mp[a] = b
    return mp


def _offset_formulas():
    """offset(di,dj) 후보식 — {0,±1, H-1,W-1, -uppermost,-leftmost, H-h,W-w} 조합(§4-1). 손계산 금지."""
    comp = {
        "0": lambda H, W, oh, ow, u, l: 0,
        "1": lambda H, W, oh, ow, u, l: 1,
        "-1": lambda H, W, oh, ow, u, l: -1,
        "H-1-u": lambda H, W, oh, ow, u, l: H - 1 - u,      # 하단 코너로
        "W-1-l": lambda H, W, oh, ow, u, l: W - 1 - l,      # 우측 코너로
        "-u": lambda H, W, oh, ow, u, l: -u,               # 상단
        "-l": lambda H, W, oh, ow, u, l: -l,               # 좌측
    }
    return comp


def _apply_translate(name, grid, sel, di_f, dj_f):
    """sel(=선택규칙), offset 식을 grid 에 적용. 실패(obj 없음/여럿)면 None."""
    objs = [d["obj"] for d in find_all_objects(grid) if d["method"]["without_bg"]]
    objs = [o for o in objs if len(o) > 0]
    if sel == "single" and len(objs) != 1:
        return None
    if not objs:
        return None
    obj = max(objs, key=len) if sel == "largest" else objs[0]
    rows = [i for _, (i, _) in obj]; cols = [j for _, (_, j) in obj]
    u, l = min(rows), min(cols)
    oh, ow = max(rows) - u + 1, max(cols) - l + 1
    H, W = len(grid), len(grid[0])
    di, dj = di_f(H, W, oh, ow, u, l), dj_f(H, W, oh, ow, u, l)
    return body(name)(grid, obj, (di, dj))


def _arg_plans(name, train):
    """DSL 이름별 arg 후보 plan 목록 산출. plan={apply: grid->grid|None, args, src}.
    ①relation 즉시(recolor) ②selection ③표현식탐색(translate). param-free 는 인자 없음."""
    verb = SPECS[name]["effect"]["verb"]
    if verb in ("rotate", "reflect", "downscale", "crop"):
        return [{"apply": (lambda g, n=name: body(n)(g)), "args": [], "src": "param-free"}]
    if verb == "recolor":
        mp = _recolor_map(train)
        if not mp:
            return []
        diff = [(a, b) for a, b in mp.items() if a != b]
        plans = []
        if name == "replace" and len(diff) == 1:
            a, b = diff[0]
            plans.append({"apply": (lambda g, a=a, b=b: body("replace")(g, a, b)),
                          "args": [a, b], "src": "relation(color-DIFF)"})
        if name == "switch" and len(diff) == 2 and diff[0] == (diff[1][1], diff[1][0]):
            a, b = diff[0]
            plans.append({"apply": (lambda g, a=a, b=b: body("switch")(g, a, b)),
                          "args": [a, b], "src": "relation(color-DIFF)"})
        return plans
    if verb == "translate":
        comp = _offset_formulas()
        plans = []
        for sel in ("single", "largest"):
            for din, dif in comp.items():
                for djn, djf in comp.items():
                    plans.append({
                        "apply": (lambda g, n=name, s=sel, a=dif, b=djf: _apply_translate(n, g, s, a, b)),
                        "args": [sel, f"di={din}", f"dj={djn}"], "src": "search(offset)"})
        return plans
    return []


def transform_search(train):
    required = derive_required_effect(train)
    cands = candidate_transforms(required)
    hyps, survivor = [], None
    for name in cands:
        plans = _arg_plans(name, train)
        if not plans:
            hyps.append({"rule": name, "args_src": None, "verdict": "reject", "why": "arg 미해결"})
            continue
        for plan in plans:
            try:
                ok = all(plan["apply"](e["input"]) == e["output"] for e in train)
            except Exception:
                ok = False
            hyps.append({"rule": name, "args_src": plan["src"], "args": plan["args"],
                         "verdict": "survive" if ok else "reject"})
            if ok and survivor is None:
                survivor = {"rule": name, "plan": {"args": plan["args"], "src": plan["src"]}}
    return {"required": [e["verb"] for e in required], "candidates": cands,
            "hypotheses": hyps, "survivor": survivor}
