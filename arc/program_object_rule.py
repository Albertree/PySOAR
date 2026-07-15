# -*- coding: utf-8 -*-
"""
program_object_rule -- PROTOTYPE (2026-07-13). object 제자리 재채색을, **ARCKG property +
compare(COMM/DIFF) + arithmetic** 원시정보의 조합만으로 표현한다 (자연어 라벨·새 concept 최소화).

한 object 의 특징 = 그 object 를 (발견된) 그룹의 나머지와 **`compare` 한 결과들의 집합**:
  compare(O, O') → 속성별 {COMM|DIFF}. 숫자 property 의 DIFF 는 arithmetic 으로 부호(> / <)까지.
이 **compare 결과 집합(signature)** 이 색을 정한다. pair 간 같은 signature → 같은 색(= 2차 compare
로 COMM). test 에서도 각 object 의 signature 를 만들어 규칙에 매칭. "largest"·"∀ greater"·"count"
같은 이름/자연어를 쓰지 않는다 — 전부 (property, COMM/DIFF, 부호) 튜플의 조합으로만.

그룹도 하드코딩하지 않는다: `compare(O,X).color == COMM` 를 만족하는 X 들, 처럼 **COMM 술어**로 발견.
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root

import arc.dsl  # noqa: F401,E402  (ARC-solver 를 sys.path 에)
from arc.select_solver import fg_objects        # noqa: E402
from ARCKG.comparison import _compare_dicts      # noqa: E402  (COMM/DIFF 엔진)

# arithmetic 부호를 매길 수 있는(=순서 있는) property 들.
ORD = {
    "area":   lambda o: o["area"],
    "height": lambda o: max(o["rows"]) - min(o["rows"]) + 1,
    "width":  lambda o: max(o["cols"]) - min(o["cols"]) + 1,
}


def _bg(g):
    return Counter(v for row in g for v in row).most_common(1)[0][0]


def _oprops(o):
    r0 = min(c[0] for c in o["cells"]); c0 = min(c[1] for c in o["cells"])
    return {"color": o["color"], "area": o["area"],
            "height": max(c[0] for c in o["cells"]) - r0 + 1,
            "width": max(c[1] for c in o["cells"]) - c0 + 1,
            "shape": sorted([c[0] - r0, c[1] - c0] for c in o["cells"])}


def _cmp(o, x):
    """ARCKG compare → {property: 'COMM'|'DIFF'}."""
    return {k: v["type"] for k, v in _compare_dicts(_oprops(o), _oprops(x))["category"].items()}


# 비교 그룹: 하드코딩 대신 COMM 술어로 발견. (property, COMM 요구) 로 그룹을 정의.
GROUPS = [
    ("compare(·).color=COMM", lambda o, rec: [x for x in rec if _cmp(o, x).get("color") == "COMM"]),
    ("group=all",             lambda o, rec: list(rec)),
]


def _signature(o, group, P, key):
    """O 를 그룹의 각 O' 와 compare 한 결과의 집합(정렬 튜플): (P,COMM) 또는 (P,DIFF,'>'/'<').
    부호는 DIFF 를 arithmetic 으로 분석한 것(§4-2). 자연어·이름 없음 — 원시 compare 결과뿐."""
    sig = []
    for x in group:
        if x is o:
            continue
        if _cmp(o, x).get(P) == "COMM":
            sig.append((P, "COMM"))
        else:
            sig.append((P, "DIFF", ">" if key(o) > key(x) else "<"))
    return tuple(sorted(sig))


def sig_str(sig):
    """signature 를 원시 튜플 그대로 렌더 (자연어 아님)."""
    return " ".join(f"{s[0]}:{s[1]}{s[2] if len(s) > 2 else ''}" for s in sig)


def _objs_newcolor(pair):
    ins = fg_objects(pair["input"], "G0")
    out = pair["output"]
    if len(ins) < 2 or len(out) != len(pair["input"]) or len(out[0]) != len(pair["input"][0]):
        return None
    bg = _bg(out)
    res, objcells = [], set()
    for o in ins:
        cols = {out[r][c] for (r, c) in o["cells"]}
        if len(cols) != 1:
            return None
        nc = next(iter(cols))
        if nc == bg:
            return None
        res.append((o, nc))
        objcells.update((r, c) for (r, c) in o["cells"])
    for r in range(len(out)):
        for c in range(len(out[0])):
            if (r, c) not in objcells and out[r][c] != pair["input"][r][c]:
                return None
    return res


def solve_recolor_rank(task):
    """제자리 재채색 + '새색 = f(compare-signature on P within 발견된 그룹)' 규칙 탐색."""
    train = task["train"]
    for gname, gpred in GROUPS:                          # 그룹 발견 (COMM 술어)
        for P, key in ORD.items():                       # 어떤 property 로 compare 할지 발견
            mapping, trace, ok = {}, [], True
            for pair in train:
                ov = _objs_newcolor(pair)
                if not ov:
                    ok = False
                    break
                rec = [o for o, _ in ov]
                prow = []
                for o, nc in ov:
                    sig = _signature(o, gpred(o, rec), P, key)
                    prow.append({"val": key(o), "sig": sig, "color": nc})
                    if mapping.get(sig, nc) != nc:
                        ok = False
                        break
                    mapping[sig] = nc
                trace.append(prow)
                if not ok:
                    break
            if not ok:
                continue
            if len(set(mapping.values())) < 2:           # signature 가 색을 실제로 구분해야
                continue
            tp = task["test"][0]
            tobjs = fg_objects(tp["input"], "G0")
            out = [row[:] for row in tp["input"]]
            ttrace, good = [], len(tobjs) > 0
            for o in tobjs:
                sig = _signature(o, gpred(o, tobjs), P, key)
                ttrace.append({"val": key(o), "sig": sig, "color": mapping.get(sig)})
                if sig not in mapping:
                    good = False
                    break
                for (r, c) in o["cells"]:
                    out[r][c] = mapping[sig]
            return {"prop": P, "group": gname,
                    "map": [(sig_str(k), v) for k, v in mapping.items()],
                    "train_trace": trace, "test_trace": ttrace,
                    "test_output": out if good else None, "expected": tp.get("output")}
    return None
