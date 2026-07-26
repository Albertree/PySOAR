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
    # resolve 실패(slot 을 G0 유래식으로 못 세움)도 generalize 실패와 같은 dead-end 이다: apply_solution
    # 은 resolved:yes 를 요구하므로 발화하지 않아 답이 안 나온다. 이때 generalize 실패 브랜치와 동일한
    # needs-transform 신호를 세워 좌표식 해 도출(transform operator)로 넘긴다(옛 fallback 이 덮던 경로 —
    # 새 property 아님, 기존 신호 재사용). transform 이 소진/해없음이면 스스로 transformed 로 되돌린다.
    if not ok_all and not ag.wm.contains(sid, "transformed", "yes"):
        ag.wm.add(sid, "needs-transform", "yes")
