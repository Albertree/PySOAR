# -*- coding: utf-8 -*-
"""ARBOR operator body: verify (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning.program import _materialize_pair_programs


def _op_verify(ag):
    """**verify operator (apply body)** — 시뮬 grid 를 train output 과 대조(원자). 같으면
    (sid ^hypothesized yes) + PAIR.program 채움, 아니면 (sid ^hypothesized failed → main 이 PIXEL 하강).
    성공 시 **존재하는 모든 PAIR** 에 per-pair program 을 물질화(_materialize_pair_programs, §2-5 반영)."""
    sid = ag.stack[-1].id
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in (sim or [])]
    out = ag.task["train"][0]["output"]
    pid = next((v for (i, a, v) in ag.wm if i == sid and a == "sim-pair"), None)
    if grid == [list(r) for r in out]:
        ag.wm.add(sid, "hypothesized", "yes")
        code = next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), "output_grid = input_grid")
        if pid:
            ppid = f"{pid}.property"
            if ag.wm.contains(ppid, "program", "{}"):
                ag.wm.remove(ppid, "program", "{}")
            ag.wm.add(ppid, "program", code)               # 실행가능 flat Python (level-1 형식)
        _materialize_pair_programs(ag)                      # 나머지 PAIR 들도 program 물질화(N개)
    else:
        ag.wm.add(sid, "hypothesized", "failed")
