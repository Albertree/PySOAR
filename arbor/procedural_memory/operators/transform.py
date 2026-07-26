# -*- coding: utf-8 -*-
"""ARBOR operator body: transform (좌표식 해 도출, procedural LTM leaf).

anti-unify(generalize)가 per-pixel 정렬로는 공통 골격을 못 세우고 compress(덩어리화)도
적용 안 되는 op-불일치 태스크에서, **좌표식/선형 D4/객체선택 변환** 후보들을 primitive
조합으로 탐색·검증해(§arbor.reasoning.transform) 답 격자 후보들을 낸다. 이름 "transform"
은 변환 '종류'가 아니라 '좌표식 해를 도출한다'는 뜻(개념명 금지 §2).

handshake(apply_solution 미러 — ARC 3-attempt): generalize 실패 브랜치가 needs-transform 을
세우면 발화 → `transform_candidates` 로 후보 격자 리스트를 **1회 계산·캐시**하고, 매 발화마다
`candidates[idx]` 를 answer 로 물질화(answer-ready). 오답이면 `_reject_and_retry` 가 idx+1 +
answer-ready 제거 + operator 해제 → needs-transform 이 남아 있어 **재발화**해 다음 후보를 낸다.
후보가 없으면 정직히 generalized:failed, 소진되면 hyps-exhausted 로 종결하며 그때에만
needs-transform 을 제거한다(정상 경로에선 유지 — 재발화용).
"""
from __future__ import annotations

import json
from arbor.reasoning.transform import transform_candidates, transform_solution_ast


def _drop_needs_transform(ag, sid):
    for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-transform")):
        ag.wm.remove(i, a, v)


def _op_transform(ag):
    """**transform operator (apply body)** — 후보 격자들을 탐색해 idx 순으로 answer 물질화(ARC 3-attempt).
    후보 없음=generalized:failed(정직한 impasse), 소진=hyps-exhausted. 정상 경로선 needs-transform 을
    유지해 오답 시 재발화, transformed 는 설정하지 않는다."""
    sid = ag.stack[-1].id
    S = ag.kg.setdefault("solve", {})
    root = ag.kg.get("arckg_root")

    # ── 최초 진입(mode 미설정): 후보 리스트를 1회 계산·캐시 + 표시용 해 아티팩트 1회 물질화.
    if S.get("mode") != "transform":
        train = [(e["input"], e["output"]) for e in (ag.task.get("train") or [])]
        test = ag.task.get("test") or []
        if root is None or not train or not test:            # 관측 불가 = 정직한 impasse
            _drop_needs_transform(ag, sid)
            ag.wm.add(sid, "generalized", "failed")
            ag.wm.add(sid, "transformed", "yes")
            return
        test_input = test[0]["input"]
        cands = transform_candidates(train, test_input)
        S["mode"] = "transform"
        S["hyps"] = [{"label": f"transform#{i + 1}"} for i in range(len(cands))]
        S["transform_grids"] = cands
        S["idx"] = 0
        # 표시용 해 아티팩트(display) — 답 생성엔 무관, 리포트 물질화용. 해당 AST 없으면 생략.
        res = transform_solution_ast(train, test_input)
        if res is not None:
            solution_ast, _answer = res
            tpid = f"{root.node_id}.property"
            old = next((v for (i, a, v) in ag.wm if i == tpid and a == "solution"), None)
            if old in (None, "{}"):
                ag.wm.remove(tpid, "solution", old)          # 저장된 sentinel 제거
            ag.wm.add(tpid, "solution", json.dumps(solution_ast))

    idx = S.get("idx", 0)
    cands = S.get("transform_grids") or []

    if not cands:                                            # 해 없음 = 정직한 impasse
        _drop_needs_transform(ag, sid)
        ag.wm.add(sid, "generalized", "failed")
        ag.wm.add(sid, "transformed", "yes")
        return
    if idx >= len(cands):                                    # 후보 소진
        _drop_needs_transform(ag, sid)
        ag.wm.add(sid, "hyps-exhausted", "yes")
        return

    # ── 정상: candidates[idx] 를 answer 로 물질화. needs-transform 은 유지(오답 시 재발화), transformed 미설정.
    grid = cands[idx]
    ag.kg["answer"] = grid
    ag.add_output_wme("answer", tuple(tuple(r) for r in grid))   # output-link 방출
    ag.wm.add(sid, "answer-ready", "yes")                        # → propose*submit
    S["idx"] = idx
    S["verified"] = {"position": f"transform#{idx + 1}", "color": ""}
    ag.kg["transform"] = {"tid": getattr(root, "node_id", None), "answer": grid, "idx": idx}
