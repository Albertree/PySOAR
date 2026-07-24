# -*- coding: utf-8 -*-
"""ARBOR operator body: select (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from arbor.soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.perception.nav import _focus_group
from arbor.procedural_memory.operators.observe import _build_agenda


def _op_select(ag):
    """**arg-선택 substate 의 operator.** observe/compare 가 arg 없이 propose 되어 걸린 impasse 를
    푼다 — superstate 의 다음 관측/비교 대상을 preference(순서상 **첫 미완료** = a안)로 골라 super 의
    ^cursor / ^cmp-active 를 세운다. 그러면 super 의 observe/compare 가 그 arg 로 apply 가능해져
    impasse 가 해소되고 substate 는 pop 된다(fine_trace). §1-3 의 '후보 탐색'은 이 body 에 얹을 자리.
      select-for observe: 다음 미관측 focus → super ^cursor. 없으면 super ^observed + 비교 agenda.
      select-for compare: 다음 미완료 cmp → super ^cmp-active. 없으면 super ^compared."""
    sid = ag.stack[-1].id                                        # 현재 = arg-선택 substate
    sup = next((v for (i, a, v) in ag.wm if i == sid and a == "superstate"), None)
    idx = ag.kg.get("idx") if getattr(ag, "kg", None) else None
    # 무엇을 고를지는 **WM 상태에서 추론**한다 (select-for 값에 의존하지 않음, 사용자 요청):
    #   미관측 focus 노드가 있으면 → 관측 대상(super ^cursor). 관측이 다 끝났으면(없으면) → observed 전환
    #   후, 미완료 cmp 를 비교 대상(super ^cmp-active), 그것도 없으면 compared. (관측이 비교보다 먼저 오므로
    #   'unseen 유무 → observed → cmp' 우선순위가 기존 select-for observe/compare 분기를 그대로 재현.)
    unseen = sorted(n for n in _focus_group(ag, sup) if not ag.wm.contains(n, "seen", "yes"))
    if unseen:                                                   # (A) 관측 대상: 소속 순서(노드 id 정렬)로 첫 미관측
        target = unseen[0]
        ag.wm.add(sup, "cursor", target)                        # super 커서 = 첫 미관측(정렬순 = 부모별 묶임)
        # (B) 상위 level cursor 유지: 관측 대상의 부모를 그 부모를 ^focus 로 가진 goal 의 ^cursor 로 세워
        #     하강해도 소속 path 가 상위 level 에 남게 한다.
        par = idx["parent"].get(target) if idx else None
        pgoal = next((i for (i, a, v) in ag.wm if a == "focus" and v == par), None) if par else None
        if pgoal is not None:
            for (i, a, v) in list(ag.wm):
                if i == pgoal and a == "cursor":
                    ag.wm.remove(i, a, v)
            ag.wm.add(pgoal, "cursor", par)
    elif not ag.wm.contains(sup, "observed", "yes"):            # 다 관측 → 비교 국면 전환
        ag.wm.add(sup, "observed", "yes")
        _build_agenda(ag, sup, _focus_group(ag, sup))            # (sup ^cmp ..) + ^to-compare
    else:                                                        # 관측 끝 → 비교 대상: 미완료 cmp 중 첫(order)
        pend = [(int(next(v for (i2, a2, v) in ag.wm if i2 == cid and a2 == "order")), cid)
                for (i, a, cid) in ag.wm if i == sup and a == "cmp"
                and not ag.wm.contains(cid, "done", "yes")]
        if pend:
            pend.sort(); ag.wm.add(sup, "cmp-active", pend[0][1])
        else:
            ag.wm.add(sup, "compared", "yes")
    ag.wm.add(sid, "selected", "yes")                            # 이 substate 는 대상 정함 → retract → pop
