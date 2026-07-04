# -*- coding: utf-8 -*-
"""
solve_ops -- 풀이 파이프라인의 생각 operator body (find·hypothesize·predict·
evaluate·verify·compose·submit). 각 operator 는 focus_solver 에서 propose+apply
규칙을 갖는다; 여기 body 는 그 규칙이 발화할 때 도는 RHS-function 이다.

원칙:
  - 고정 시나리오가 아니다. 이 operator 들은 *발견된 goal(^produce)* 이 있는 substate
    에서만 발화하고, "이 레벨에서 풀이를 시도 → 실패하면 solve(미구현)로 하강" 이라는
    impasse 구조를 따른다 (hypothesize 가 안 통하면 hyps-exhausted → solve fallback).
  - 근거만 사용: 가설/조립은 predefined DSL(arc/dsl: 2 frozen transformation +
    argument 표현식 resolve)만 쓴다. 새 변환/DSL 을 지어내지 않는다.
  - generate-and-test 가 눈에 보인다: hypothesize 가 후보를 랭킹 → predict/evaluate 가
    train 오라클로 하나씩 채점(틀리면 다음 후보) → verify → compose → submit.
"""
from __future__ import annotations

from arc.select_solver import fg_objects                      # 전경 object 추출(predefined)
from arc.dsl import (context, grid_bg, ranked_hypotheses,      # predefined DSL 기계
                     build_from_hypothesis)
from arc.expr_solver import _lone, _target_and_others, _pick_target
from arc import relation_solve                                 # structure-mapping 관계 일반화


def _sid(ag):
    return ag.stack[-1].id                                     # 현재 substate(=goal 보유)


def _name(h):
    return f"{h['position']} | {h['color']}"


# ---------------------------------------------------------------------------
# train pair 로부터 (per-pair 샘플 + test ctx) 를 만든다 -- expr_solver 와 동일한
# 전경 target 추출. 단일 target object 계열만 대상(그 외엔 None → 가설 없음).
# ---------------------------------------------------------------------------
def _samples_and_test(task):
    pairs, tcolors = [], set()
    for i, p in enumerate(task["train"]):
        ins = fg_objects(p["input"], f"P{i}.G0")
        tout = _lone(fg_objects(p["output"], f"P{i}.G1"))
        tin, others = _target_and_others(ins, tout)
        pairs.append({"in_raw": p["input"], "out_raw": p["output"],
                      "tin": tin, "tout": tout, "others": others})
        if tin:
            tcolors.add(tin["color"])
    if not all(pr["tin"] and pr["tout"] for pr in pairs):
        return None, None                                     # 단일 target 계열 아님
    samples = []
    for pr in pairs:
        oc = sorted(pr["tout"]["cells"])
        od = (len(pr["out_raw"]), len(pr["out_raw"][0]))
        samples.append({"ctx": context(pr["tin"], pr["in_raw"], od, others=pr["others"]),
                        "out_coord": oc[0], "out_color": pr["tout"]["color"],
                        "out_size": od, "out_bg": grid_bg(pr["out_raw"])})
    tp = task["test"][0]
    test_objs = fg_objects(tp["input"], "Pa.G0")
    test_obj = _pick_target(test_objs, tcolors)
    test_ctx = None
    if test_obj:
        test_ctx = context(test_obj, tp["input"],
                           (len(tp["output"]), len(tp["output"][0])),
                           others=[o for o in test_objs if o is not test_obj])
    return samples, {"ctx": test_ctx, "tp": tp}


# ---------------------------------------------------------------------------
# find -- object 레벨에서 aggregate 가 도출한 role(extremum+ on area)로 대상 선택.
# ("가장 큰 것을 고른다"의 selection primitive. downstream role-가설은 향후 슬라이스.)
# ---------------------------------------------------------------------------
def _op_find(ag):
    """aggregate 가 도출한 area 관계로 *전경(foreground)* 최대 object 를 고른다.
    배경/전체격자 object 는 제외(색이 배경색뿐이면 전경 아님). '가장 큰 것을 고른다'
    를 도출된 greater 관계 위에서 실현 — 새 property 없이."""
    from arc.focus_solver import _focus, _siblings
    idx, f = ag.kg["idx"], _focus(ag)
    s = _sid(ag)
    group = [o for o in _siblings(idx, f)]

    def is_fg(oid):                              # 전경 blob = univalued(단색) ∧ 비배경색
        j = idx["nodes"][oid].to_json()          # (전체격자 O4=non-univalued, 배경 O3=색0 → 제외)
        if not j.get("method", {}).get("univalued"):
            return False
        return any(v for k, v in j.get("color", {}).items() if k not in (0, "0"))

    def area_wins(oid):                          # area 에서 다른 object 보다 큰 횟수(도출된 관계)
        return sum(1 for (_i, _a, v) in ag.wm.matching(identifier=oid, attr="greater")
                   if str(v).startswith("area"))

    fg = [o for o in group if is_fg(o)]
    if not fg:
        return
    pick = max(fg, key=area_wins)                # 전경 중 area 최대 = "가장 큰 object"
    ag.wm.add(s, "selected", pick)
    ag.kg.setdefault("selected", []).append(pick)


# ---------------------------------------------------------------------------
# hypothesize -- train pair 에서 변환 가설을 랭킹 생성 (predefined DSL 조합).
# 후보가 없으면(단일 target 계열 아님) hyps-exhausted → solve fallback 로 하강.
# ---------------------------------------------------------------------------
def _op_hypothesize(ag):
    """가설 = input→output 관계. 두 경로:
    (1) structure-mapping: G0 를 seed 로 GRID 3속성(size/color/contents) 관계를 pair 간
        일반화 (relation_solve). contents 가 잡히면 완결.
    (2) fallback: 단일 object dsl arg 합성(program synthesis)."""
    s = _sid(ag)
    prog = relation_solve.generalize(ag.task["train"])         # per-property 관계 일반화
    ag.kg["last_prog"] = relation_solve.describe(prog)         # 대시보드 3속성 슬롯
    if relation_solve.is_complete(prog):                       # contents 해소 → 완결 프로그램
        ag.kg["solve"] = {"mode": "relational", "prog": prog, "verified": None}
        desc = relation_solve.describe(prog)
        ag.wm.add(s, "hyp", "relational: " + ", ".join(f"{k}={v}" for k, v in desc.items()))
        return
    # (2) fallback: dsl 단일 object 가설
    samples, testinfo = _samples_and_test(ag.task)
    if not samples or not (hyps := ranked_hypotheses(samples)):
        ag.wm.add(s, "hyps-exhausted", "yes")                 # 관계 미완 ∧ dsl 도 불가 → 하강
        ag.kg["solve"] = {"mode": "none", "hyps": [], "idx": 0}
        return
    ag.kg["solve"] = {"mode": "dsl", "samples": samples, "test": testinfo,
                      "hyps": hyps, "idx": 0, "verified": None}
    for h in hyps[:6]:                                        # 후보를 WM 에 나열(대시보드)
        ag.wm.add(s, "hyp", _name(h))
    ag.kg["last_hyps"] = [_name(h) for h in hyps[:6]]


# ---------------------------------------------------------------------------
# predict -- 현재 후보 가설을 train 입력마다 적용(내부 시뮬레이션) → 예측 격자.
# ---------------------------------------------------------------------------
def _op_predict(ag):
    s = _sid(ag)
    S = ag.kg["solve"]
    if S["mode"] == "relational":                             # 관계를 각 train 입력에 적용
        S["predicted"] = [relation_solve.apply(S["prog"], p["input"]) for p in ag.task["train"]]
        ag.wm.add(s, "predict-hyp", "relational program")
        ag.kg["last_predict"] = {"hyp": "relational", "idx": 0}
        return
    h = S["hyps"][S["idx"]]
    S["predicted"] = [build_from_hypothesis(h, sm["ctx"]) for sm in S["samples"]]
    ag.wm.add(s, "predict-hyp", _name(h))
    ag.kg["last_predict"] = {"hyp": _name(h), "idx": S["idx"]}


# ---------------------------------------------------------------------------
# evaluate -- 예측을 train 출력(오라클)과 대조. 전부 맞으면 consistent, 아니면
# 다음 후보로(idx++). 후보 소진 시 hyps-exhausted.
# ---------------------------------------------------------------------------
def _op_evaluate(ag):
    s = _sid(ag)
    S = ag.kg["solve"]
    outs = [tp["output"] for tp in ag.task["train"]]
    ok = (S.get("predicted") is not None
          and all(S["predicted"][i] == outs[i] for i in range(len(outs))))
    if S["mode"] == "relational":                             # 관계 프로그램 하나뿐
        ag.kg["last_eval"] = {"hyp": "relational", "ok": ok, "idx": 0}
        if ok:
            S["verified"] = S["prog"]
            ag.wm.add(s, "consistent", "relational program")
        else:
            ag.wm.add(s, "hyps-exhausted", "yes")             # 관계 실패 → 하강
        return
    h = S["hyps"][S["idx"]]
    ag.kg["last_eval"] = {"hyp": _name(h), "ok": ok, "idx": S["idx"]}
    if ok:
        S["verified"] = h
        ag.wm.add(s, "consistent", _name(h))                  # train 오라클 통과
    else:
        S["idx"] += 1
        if S["idx"] >= len(S["hyps"]):
            ag.wm.add(s, "hyps-exhausted", "yes")             # 다 틀림 → 하강


# ---------------------------------------------------------------------------
# verify -- consistent 후보를 train 전체에서 최종 재확인 → verified 로 고정.
# ---------------------------------------------------------------------------
def _op_verify(ag):
    s = _sid(ag)
    S = ag.kg["solve"]
    outs = [tp["output"] for tp in ag.task["train"]]
    if S["mode"] == "relational":
        ok = all(relation_solve.apply(S["verified"], p["input"]) == outs[i]
                 for i, p in enumerate(ag.task["train"]))
        ag.kg["last_verify"] = {"hyp": "relational", "ok": ok}
        if ok:
            ag.wm.add(s, "verified", "relational program")
        return
    h = S["verified"]
    ok = all(build_from_hypothesis(h, sm["ctx"]) == outs[i]
             for i, sm in enumerate(S["samples"]))
    ag.kg["last_verify"] = {"hyp": _name(h), "ok": ok}
    if ok:
        ag.wm.add(s, "verified", _name(h))


# ---------------------------------------------------------------------------
# compose -- verified 가설을 test 입력에 적용해 답 격자 조립(make_grid+coloring).
# ---------------------------------------------------------------------------
def _op_compose(ag):
    s = _sid(ag)
    S = ag.kg["solve"]
    if S["mode"] == "relational":                             # 관계를 test 입력에 적용
        ans = relation_solve.apply(S["verified"], ag.task["test"][0]["input"])
    else:
        ctx = (S.get("test") or {}).get("ctx")
        ans = build_from_hypothesis(S["verified"], ctx) if ctx else None
    if ans:
        ag.kg["answer"] = ans
        ag.add_output_wme("answer", tuple(tuple(r) for r in ans))   # → output-link
        ag.wm.add(s, "answer-ready", "yes")
    else:
        ag.wm.add(s, "declined", "yes")


# submit 은 body 없음: apply*submit 이 ^done 을 쓰고, 답은 이미 output-link 에 있음.
SOLVE_BODIES = {
    "find": _op_find, "hypothesize": _op_hypothesize, "predict": _op_predict,
    "evaluate": _op_evaluate, "verify": _op_verify, "compose": _op_compose,
}


def solve_detail(kg, op):
    """대시보드 하단 패널(생각 operator)."""
    if op == "hypothesize":
        return {"kind": "hypothesize", "hyps": kg.get("last_hyps", []),
                "program": kg.get("last_prog")}     # GRID 3속성(size/color/contents) 관계
    if op == "predict":
        return {"kind": "predict", "info": kg.get("last_predict")}
    if op == "evaluate":
        e = kg.get("last_eval") or {}
        return {"kind": "evaluate", "hyp": e.get("hyp"), "ok": e.get("ok"), "idx": e.get("idx")}
    if op == "verify":
        return {"kind": "verify", "info": kg.get("last_verify")}
    if op == "compose":
        return {"kind": "compose", "answer": kg.get("answer")}
    if op == "find":
        return {"kind": "find", "selected": [s.split(".")[-1] for s in kg.get("selected", [])]}
    return {"kind": op}
