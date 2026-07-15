# -*- coding: utf-8 -*-
"""ARBOR operator body: verify (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations

from procedural_memory.operators.hypothesize import pair_cursor
from arbor.reasoning.program_ast import as_source


def _op_verify(ag):
    """**verify operator (apply body)** — 시뮬 grid 를 현재 pair(커서)의 train output 과 대조(원자).
    같으면 (sid ^hypothesized yes) + 그 PAIR.program 채움. 이후:
      - 아직 program 공백인 example pair 가 남았으면 → 커서 +1 + 합성 플래그 리셋 → hypothesize 가
        다음 pair 로 흐름을 **다시** 탄다 (§1-5: 각 program 이 operator 흐름에서 나온다).
      - 모든 example pair 에 program → programs-ready(≥2) → generalize.
    틀리면 (sid ^hypothesized failed → main 이 PIXEL 하강)."""
    sid = ag.stack[-1].id
    k = pair_cursor(ag)
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in (sim or [])]
    out = ag.task["train"][k]["output"]
    pid = next((v for (i, a, v) in ag.wm if i == sid and a == "sim-pair"), None)
    if grid != [list(r) for r in out]:
        ag.wm.add(sid, "hypothesized", "failed")
        return
    ag.wm.add(sid, "hypothesized", "yes")
    code = as_source(next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), None))
    if code == "{}":
        code = "output_grid = input_grid"
    if pid:
        ppid = f"{pid}.property"
        if ag.wm.contains(ppid, "program", "{}"):
            ag.wm.remove(ppid, "program", "{}")
        ag.wm.add(ppid, "program", code)                      # 실행가능 flat Python (level-1)
    _advance_or_finish(ag, sid, k)


def _advance_or_finish(ag, sid, k):
    root = ag.kg.get("arckg_root")
    pairs = list(getattr(root, "example_pairs", []) or [])
    npairs = min(len(pairs), len(ag.task["train"]))
    if k + 1 < npairs:                                        # 다음 pair 로 순회
        for (i, a, v) in list(ag.wm.matching(identifier="S1", attr="pair-idx")):
            ag.wm.remove(i, a, v)
        ag.wm.add("S1", "pair-idx", str(k + 1))
        _reset_synth(ag, sid)                                 # 합성 플래그 리셋 → hypothesize 재발화
        return
    # 마지막 pair 완료 → 모든 program 존재 시 generalize 트리거
    have = 0
    for pp in pairs[:npairs]:
        v = next((x for (i, a, x) in ag.wm if i == f"{pp.node_id}.property" and a == "program"), None)
        if v not in (None, "{}"):
            have += 1
    if have >= 2 and not ag.wm.contains(sid, "programs-ready", "yes"):
        ag.wm.add(sid, "programs-ready", "yes")


def _reset_synth(ag, sid):
    """다음 pair 를 위해 합성 결과 플래그를 지운다 → hypothesize propose 재매치. o-support(apply
    규칙이 assert 한 hyp-open 등)는 elaborator.o_support_wmes 에서도 제거(재확립 방지)."""
    elab = getattr(ag, "elaborator", None)

    def drop(i, a, v):
        ag.wm.remove(i, a, v)
        if elab is not None:
            elab.o_support_wmes.discard((i, a, v))

    for attr in ("hypothesized", "hyp-open", "colored-all", "sim", "sim-pair",
                 "program-code", "base-program", "has-recolor"):
        for (i, a, v) in list(ag.wm.matching(identifier=sid, attr=attr)):
            drop(i, a, v)
    for (i, a, x) in list(ag.wm.matching(identifier=sid, attr="xform")):     # xform 마커 + 하위
        drop(i, a, x)
        for (xi, xa, xv) in list(ag.wm.matching(identifier=x)):
            drop(xi, xa, xv)
