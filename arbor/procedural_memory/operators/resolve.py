# -*- coding: utf-8 -*-
"""ARBOR operator body: resolve (변수 origin, procedural LTM leaf).

TASK.solution 의 각 변수 slot 을 **G0 유래 표현식**으로 resolve 한다: 후보식 생성 →
각 train pair 의 G0 에 적용 → slot 의 DIFF 값과 대조 → 기각/생존(version space).
test 출력을 오라클로 쓰지 않는다(§P5). 시도·기각은 대시보드에 남는다(§1-3/§1-5).
"""
from __future__ import annotations

from arbor.reasoning.antiunify import resolve_slot


def _op_resolve(ag):
    sid = ag.stack[-1].id
    sol = ag.kg.get("solution")
    if not sol:
        ag.wm.add(sid, "resolved", "failed")
        return
    slots = sol.get("slots") or {}
    tpid = f"{sol['tid']}.property"
    if not slots:                                    # 변수 없음 → 바로 resolved
        sol["resolved"] = {}
        ag.wm.add(sid, "resolved", "yes")
        return
    train = ag.task["train"]
    test = ag.task.get("test") or []
    test_input = test[0].get("input") if test else None   # 추상화를 test 입력에 검증(§사용자 #2; P5=출력만 금지)
    resolved, tried_all, ok_all = {}, {}, True
    for name, slot in slots.items():
        survivors, tried = resolve_slot(slot, train, test_input)
        tried_all[name] = tried
        if survivors:
            resolved[name] = survivors               # version space (생존 후보들)
            ag.wm.add(tpid, "resolved", f"{name}={survivors[0][0]}")   # 대표 식(근거)
        else:
            ok_all = False
    sol["resolved"] = resolved
    ag.kg["resolve"] = {"resolved": {n: v[0][0] for n, v in resolved.items()},
                        "tried": tried_all}
    ag.wm.add(sid, "resolved", "yes" if ok_all else "failed")
