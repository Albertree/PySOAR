# -*- coding: utf-8 -*-
"""ARBOR operator body: generalize (anti-unification, procedural LTM leaf).

per-pair `PAIR.program` 들을 anti-unify 해 `TASK.solution`(골격 + 변수 slot)을 물질화한다.
COMM 라인은 상수로 고정, DIFF 라인은 변수 slot(per-pair 값 = 근거). 변수 resolve(G0 유래
표현식 탐색)는 다음 resolve operator 가 한다. (하네스 §0.5 가로축, §2-2 근거=compare.)
"""
from __future__ import annotations

from arbor.reasoning.antiunify import antiunify, render_skeleton, compressible
from arbor.reasoning.program_ast import as_source


def _op_generalize(ag):
    sid = ag.stack[-1].id
    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "generalized", "failed")
        return
    tid = root.node_id
    # 존재하는 example-pair program 들(공백 제외)을 순서대로 수집
    progs = []
    for p in getattr(root, "example_pairs", []) or []:
        ppid = f"{p.node_id}.property"
        code = as_source(next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None))
        if code == "{}":
            code = None
        if code and code != "{}":
            progs.append(code)
    sk, slots = antiunify(progs)
    if sk is None:                                        # 구조 불일치/부족
        # op 수 불일치(객체 크기 차이 등)면 정직히 포기하기 전에 compress(덩어리화) 를 신호한다.
        # compress 가 blob 으로 재작성 → generalize 재발화 → blob anti-unify. 한 번만(compressed 가드).
        if not ag.wm.contains(sid, "compressed", "yes") and compressible(progs):
            ag.wm.add(sid, "needs-compress", "yes")
            return
        ag.wm.add(sid, "generalized", "failed")
        return
    solution = render_skeleton(sk, slots)
    tpid = f"{tid}.property"
    if ag.wm.contains(tpid, "solution", "{}"):
        ag.wm.remove(tpid, "solution", "{}")
    ag.wm.add(tpid, "solution", solution)                 # TASK.solution 물질화(§2-5)
    for name, s in slots.items():                         # slot 근거 = DIFF per-pair 값
        ag.wm.add(tpid, "slot", f"{name}[{s['kind']}]=DIFF{s['values']}")
    # 파싱된 스키마·slot 은 resolve 가 쓴다 (복합구조 → kg; WM 엔 문자열 요약)
    ag.kg["solution"] = {"skeleton": sk, "slots": slots, "programs": progs, "tid": tid}
    ag.kg["generalize"] = {"solution": solution,
                           "slots": {n: s["values"] for n, s in slots.items()}}
    ag.wm.add(sid, "generalized", "yes")
