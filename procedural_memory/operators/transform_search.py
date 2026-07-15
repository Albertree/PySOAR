# -*- coding: utf-8 -*-
"""ARBOR operator body: transform_search — synthesize 의 contents-DESCEND 공백에서 DSL transform 탐색.
effect 일치 후보를 열거→arg resolve→train verify. 시도·기각을 hypothesis WME 로 잔존(§1-5)."""
from __future__ import annotations
from arbor.reasoning.transform_search import transform_search


def _op_transform_search(ag):
    s = ag.stack[-1].id
    # transform_search 는 substate 를 push 하지 않는다 — kernel 이 s 위에서 in-place 로 select+apply.
    # 따라서 s 자신이 synthesize 가 ^transform-search-open 을 쓴 "부모"(=GRID goal 보유 상태)다.
    # superstate(s) 로 올리면 answer-ready 가 조부모로 새어 generalize/resolve/compose 의
    # ^answer-ready 게이트를 무력화한다(리뷰 지적 Critical). synthesize contents-DECIDE 분기의
    # ag.wm.add(parent, "answer-ready", ...) 와 같은 레벨(=s)에 써야 한다.
    parent = s
    res = transform_search(ag.task["train"])
    ag.wm.add(s, "required-effect", "/".join(res["required"]) or "(none)")
    ag.wm.add(s, "candidates", ",".join(res["candidates"]) or "(none)")
    for k, h in enumerate(res["hypotheses"], 1):
        hh = f"{s}.T{k}"
        ag.wm.add(s, "hypothesis", hh)
        ag.wm.add(hh, "rule", h["rule"])
        ag.wm.add(hh, "args", str(h.get("args", [])))
        ag.wm.add(hh, "src", str(h.get("args_src")))
        ag.wm.add(hh, "verdict", h["verdict"])
    if res["survivor"]:
        sv = res["survivor"]
        ag.wm.add(parent, "transform-survivor", f"{sv['rule']} {sv['plan']['args']}")
        ag.wm.add(parent, "answer-ready", "yes")
    else:
        ag.wm.add(parent, "transform-verdict", "생존 후보 없음 → 하강")
    ag.wm.add(s, "transform-search-done", "yes")
