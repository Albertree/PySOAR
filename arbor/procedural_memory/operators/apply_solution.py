# -*- coding: utf-8 -*-
"""ARBOR operator body: apply_solution (TASK.solution → test 답 조립·제출, procedural LTM leaf).

resolve 된 `TASK.solution` 을 **test 입력(Pa.G0)에 실행**해 답 격자를 만들고 output-link 에
얹어 `^answer-ready` → 기존 submit 이 발화·채점. version space 가 여럿이면 최대 3후보를
retry 후보로 남긴다(ARC 3회 프로토콜). test 출력은 실행에 쓰지 않는다(§P5).
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import solution_candidates        # 유지(version space)
from arbor.reasoning.program_ast import execute
from arbor.reasoning.transform import transform_candidates_invariant   # 불변-근거 transform 우선편입


def _op_apply_solution(ag):
    sid = ag.stack[-1].id
    sol = ag.kg.get("solution")
    if not sol or "resolved" not in sol:
        ag.wm.add(sid, "apply-solution-failed", "yes")
        return
    cands = solution_candidates(sol)                     # version space 곱(≤3)
    if not cands:
        ag.wm.add(sid, "apply-solution-failed", "yes")
        return
    S = ag.kg.setdefault("solve", {})
    test_input = ag.task["test"][0]["input"]
    # ── 최초 진입(grids 미계산): 후보 격자 리스트를 1회 선계산. 불변-근거 transform 후보(D4+중심보존,
    #    관찰된 compare 불변)를 **우선** 두고, 그 뒤에 version-space 답을 잇는다. 순서유지·중복제거·≤3.
    #    move 태스크에선 transform 후보=[] 라 all_grids=version-space 그대로 → 기존 동작과 바이트 동일.
    if "grids" not in S:
        train = [(e["input"], e["output"]) for e in ag.task["train"]]
        tgrids = transform_candidates_invariant(train, test_input)          # 우선(불변-근거)
        vgrids = [execute(sol["skeleton"], test_input, choice=c) for _l, c in cands]
        all_grids = []
        for g in tgrids + vgrids:                        # tgrids 먼저 = 우선순위, 순서유지 dedup
            if g not in all_grids:
                all_grids.append(g)
        S["grids"] = all_grids[:3]                        # ARC 3-attempt cap
        S["mode"] = "antiunify"
        S["hyps"] = [{"label": f"cand#{i + 1}"} for i in range(len(S["grids"]))]
        S["idx"] = 0
    idx = S.get("idx", 0)                                 # retry 시 _reject_and_retry 가 idx+1
    grids = S["grids"]
    if idx >= len(grids):
        ag.wm.add(sid, "hyps-exhausted", "yes")
        return
    grid = grids[idx]
    label = S["hyps"][idx]["label"]
    ag.kg["answer"] = grid
    ag.add_output_wme("answer", tuple(tuple(r) for r in grid))   # output-link 방출
    ag.wm.add(sid, "answer-ready", "yes")                        # → propose*submit
    # test pair(Pa) program 물질화: resolved solution 을 구체 program 으로
    root = ag.kg.get("arckg_root")
    tpa = getattr(root, "test_pair", None) or getattr(root, "test_pairs", [None])[0]
    if tpa is not None:
        ppid = f"{tpa.node_id}.property"
        old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if old in (None, "{}"):
            ag.wm.remove(ppid, "program", old)                # 실제 저장된 sentinel(None 또는 구 "{}") 제거
        test_ast = dict(sol["skeleton"]); test_ast["slots"] = sol["slots"]
        ag.wm.add(ppid, "program", json.dumps(test_ast))
    # 3-attempt: 선계산 후보를 retry 후보로 (오답 시 _reject_and_retry 가 idx+1 → apply_solution 재발화)
    S["idx"] = idx
    S["verified"] = {"position": f"solution#{idx + 1}", "color": label}
    ag.kg["apply_solution"] = {"answer": grid, "label": label}
