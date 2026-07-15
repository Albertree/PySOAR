# -*- coding: utf-8 -*-
"""ARBOR operator body: generalize (anti-unification, procedural LTM leaf).

per-pair `PAIR.program`(AST) 들을 anti-unify 해 `TASK.solution`(골격 + 변수 slot)을 물질화한다.
COMM=상수 고정, DIFF=변수 slot(per-pair 값=근거). resolve(G0 유래 식)는 다음 operator. (§0.5·§2-2)

Task 8 보강: op 수 불일치로 antiunify_ast 가 (None,None) 을 내면, 정직히 실패하기 전에
`compressible`(레거시 antiunify.py 재사용 — 그 함수는 flat 텍스트 program 을 받으므로 `as_source`
로 렌더한 표현을 넘긴다)로 compress 신호 여부를 판정한다. 이 신호(needs-compress)가 없으면
compress operator 가 발화하지 않아 blob(object-level) program 이 만들어지지 않고, made000b 같은
op-수-불일치 태스크의 generalize 가 영구 실패한다(§2-5 행동보존).
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import compressible
from arbor.reasoning.program_ast import antiunify_ast, as_source


def _op_generalize(ag):
    sid = ag.stack[-1].id
    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "generalized", "failed")
        return
    tid = root.node_id
    # 존재하는 example-pair program(AST-json)들을 순서대로 수집 (+ compressible 용 flat 표현)
    asts, progs = [], []
    for p in getattr(root, "example_pairs", []) or []:
        ppid = f"{p.node_id}.property"
        v = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if v in (None, "{}"):
            continue
        progs.append(as_source(v))            # compressible() 은 레거시 flat 텍스트를 받는다
        try:
            ast = json.loads(v)
        except (ValueError, TypeError):
            continue
        if ast and ast.get("body"):
            asts.append(ast)
    sk, slots = antiunify_ast(asts)
    if sk is None:                                        # 구조 불일치/부족
        # op 수 불일치(객체 크기 차이 등)면 정직히 포기하기 전에 compress(덩어리화) 를 신호한다.
        # compress 가 blob 으로 재작성 → generalize 재발화 → blob anti-unify. 한 번만(compressed 가드).
        if not ag.wm.contains(sid, "compressed", "yes") and compressible(progs):
            ag.wm.add(sid, "needs-compress", "yes")
            return
        ag.wm.add(sid, "generalized", "failed")
        return
    sk_with = dict(sk); sk_with["slots"] = slots
    solution = json.dumps(sk_with)
    tpid = f"{tid}.property"
    old = next((v for (i, a, v) in ag.wm if i == tpid and a == "solution"), None)
    if old in (None, "{}") and old is not None:
        ag.wm.remove(tpid, "solution", old)
    ag.wm.add(tpid, "solution", solution)                 # TASK.solution 물질화(§2-5)
    for name, s in slots.items():                         # slot 근거 = DIFF per-pair 값
        ag.wm.add(tpid, "slot", f"{name}[{s['kind']}]=DIFF{s['values']}")
    ag.kg["solution"] = {"skeleton": sk, "slots": slots, "programs": asts, "tid": tid}
    ag.kg["generalize"] = {"solution": as_source(solution),   # 대시보드용은 flat 문자열
                           "slots": {n: s["values"] for n, s in slots.items()}}
    ag.wm.add(sid, "generalized", "yes")
