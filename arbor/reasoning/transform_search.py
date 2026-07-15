# -*- coding: utf-8 -*-
"""transform_search — COMM/DIFF 기반 effect 도출 + DSL 후보 fan-out + arg resolve/verify.
DSL 은 finder 가 아니라 search 가 열거하는 어휘. propose=effect 일치, arg=즉시|탐색, 검증=train."""
from collections import Counter
from procedural_memory.dsl.effect import effect, matches


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
