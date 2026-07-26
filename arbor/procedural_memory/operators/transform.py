# -*- coding: utf-8 -*-
"""ARBOR operator body: transform (좌표식 해 도출, procedural LTM leaf).

anti-unify(generalize)가 per-pixel 정렬로는 공통 골격을 못 세우고 compress(덩어리화)도
적용 안 되는 op-불일치 태스크에서, **하나의 공통 좌표식** `r'=F(r,c), c'=G(r,c)` 를
primitive 조합으로 탐색·검증해(§arbor.reasoning.transform) TASK.solution 을 창발시킨다.
이름 "transform" 은 변환 '종류'가 아니라 '좌표식 해를 도출한다'는 뜻(개념명 금지 §2).

handshake: generalize 실패 브랜치가 needs-transform 을 세우면 발화 → 해가 있으면
TASK.solution + test answer 를 물질화하고 answer-ready 로 종결, 없으면 정직히
generalized:failed 로 되돌린다(무한루프 방지 위해 transformed 가드). 픽셀op가 객체로
뭉치는 특정 태스크 전용이 아니라, 좌표식으로 표현되는 어떤 태스크에도 재발화한다.
"""
from __future__ import annotations

import json
from arbor.reasoning.transform import transform_solution_ast


def _op_transform(ag):
    """**transform operator (apply body)** — train 좌표식 해를 탐색해 TASK.solution + answer 물질화.
    해 없으면 generalized:failed(정직한 impasse). 신호(needs-transform) 소거·transformed 표시로
    generalize/transform 재발화(무한루프)를 막는다."""
    sid = ag.stack[-1].id
    # 신호 소거 + 재발화 가드 (해의 유무와 무관하게 항상): generalize 는 ¬transformed 일 때만
    # needs-transform 을 재emit 하고, transform propose 는 ¬transformed 로 재선택을 막는다.
    for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-transform")):
        ag.wm.remove(i, a, v)
    ag.wm.add(sid, "transformed", "yes")

    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "generalized", "failed")
        return
    tid = root.node_id
    # train = (input, output) 쌍 리스트, test 입력 = 첫 test pair (generalize/synthesize 와 동일 접근).
    train = [(e["input"], e["output"]) for e in (ag.task.get("train") or [])]
    test = ag.task.get("test") or []
    if not train or not test:
        ag.wm.add(sid, "generalized", "failed")
        return
    test_input = test[0]["input"]

    result = transform_solution_ast(train, test_input)
    if result is None:                                    # 좌표식으로 표현 불가 = 정직한 impasse
        ag.wm.add(sid, "generalized", "failed")
        return
    solution_ast, answer = result

    tpid = f"{tid}.property"                               # TASK.solution 물질화 (generalize 와 동일 shape)
    old = next((v for (i, a, v) in ag.wm if i == tpid and a == "solution"), None)
    if old in (None, "{}"):
        ag.wm.remove(tpid, "solution", old)               # 저장된 sentinel 제거
    ag.wm.add(tpid, "solution", json.dumps(solution_ast))

    # answer 는 solve_any 가 낸 권위 격자(AST 는 표시용 아티팩트) — AST 실행이 아니라 이 격자로 종결.
    ag.kg["answer"] = answer
    ag.add_output_wme("answer", tuple(tuple(r) for r in answer))
    ag.wm.add(sid, "answer-ready", "yes")
    ag.kg["transform"] = {"tid": tid, "solution": solution_ast}
