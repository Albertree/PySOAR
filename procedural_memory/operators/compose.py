# -*- coding: utf-8 -*-
"""ARBOR operator body: compose (TASK.solution → test 답 조립·제출, procedural LTM leaf).

resolve 된 `TASK.solution` 을 **test 입력(Pa.G0)에 실행**해 답 격자를 만들고 output-link 에
얹어 `^answer-ready` → 기존 submit 이 발화·채점. version space 가 여럿이면 최대 3후보를
retry 후보로 남긴다(ARC 3회 프로토콜). test 출력은 실행에 쓰지 않는다(§P5).
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import solution_candidates        # 유지(version space)
from arbor.reasoning.program_ast import execute


def _op_compose(ag):
    sid = ag.stack[-1].id
    sol = ag.kg.get("solution")
    if not sol or "resolved" not in sol:
        ag.wm.add(sid, "compose-failed", "yes")
        return
    cands = solution_candidates(sol)                     # version space 곱(≤3)
    if not cands:
        ag.wm.add(sid, "compose-failed", "yes")
        return
    S = ag.kg.setdefault("solve", {})
    idx = S.get("idx", 0)                                 # retry 시 _reject_and_retry 가 idx+1
    if idx >= len(cands):
        ag.wm.add(sid, "hyps-exhausted", "yes")
        return
    label, choice = cands[idx]
    grid = execute(sol["skeleton"], ag.task["test"][0]["input"], choice=choice)
    ag.kg["answer"] = grid
    ag.add_output_wme("answer", tuple(tuple(r) for r in grid))   # output-link 방출
    ag.wm.add(sid, "answer-ready", "yes")                        # → propose*submit
    # test pair(Pa) program 물질화: resolved solution 을 구체 program 으로
    root = ag.kg.get("arckg_root")
    tpa = getattr(root, "test_pair", None) or getattr(root, "test_pairs", [None])[0]
    if tpa is not None:
        ppid = f"{tpa.node_id}.property"
        old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if old in (None, "{}") and old is not None:
            ag.wm.remove(ppid, "program", old)
        test_ast = dict(sol["skeleton"]); test_ast["slots"] = sol["slots"]
        ag.wm.add(ppid, "program", json.dumps(test_ast))
    # 3-attempt: version space 를 retry 후보로 (오답 시 _reject_and_retry 가 idx+1 → compose 재발화)
    S["mode"] = "antiunify"
    S["hyps"] = [{"label": l} for l, _ in cands]
    S["idx"] = idx
    S["verified"] = {"position": f"solution#{idx + 1}", "color": label}
    ag.kg["compose"] = {"answer": grid, "label": label}
