# -*- coding: utf-8 -*-
"""ARBOR operator body: verify (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json

from procedural_memory.operators.hypothesize import pair_cursor
from arbor.reasoning import program_ast as PA


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
    code = next((v for (i, a, v) in ag.wm if i == sid and a == "program-code"), "output_grid = input_grid")
    if pid:
        ppid = f"{pid}.property"
        old = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        if old in (None, "{}"):
            ag.wm.remove(ppid, "program", old)                # 실제 저장된 sentinel(None 또는 구 "{}") 제거
        # grid-skeleton(hypothesize 가 parent GRID substate 에 stash — §4-2) 이 있으면 하강 coloring 을
        # 그 contents 슬롯으로 감싼 grid body(3슬롯)를, 없으면(순수 pixel 문제) 현행 pixel body 를 기록.
        ag.wm.add(ppid, "program", _assemble_pair_program(ag, code))
    _advance_or_finish(ag, sid, k)


def _find_grid_skeleton(ag):
    """PAIR.program 조립 직전, `grid-skeleton`(hypothesize.py 가 GRID substate 에 stash — §4-2)을
    조상 substate 체인에서 조회. OBJECT/PIXEL 로 하강해도 그 GRID substate 자체는 `ag.stack` 에
    남아 있다(H-space 만 purge) — 몇 hop 위인지는 하강 깊이에 따라 달라지므로 스택을 거슬러 올라가며
    찾는다(현재 substate 부터 역순 — hop 수를 가정하지 않는다)."""
    for g in reversed(ag.stack):
        v = next((v for (i, a, v) in ag.wm if i == g.id and a == "grid-skeleton"), None)
        if v is not None:
            return v
    return None


def _literal_grid_props(out):
    """그 pair 출력의 리터럴 size/color leaf (예측·pending 아님 — 실제값). size/color 는 실행에
    안 쓰이는 '선언'(§Round-3 Grid 객체모델; _execute_grid 은 contents 로만 산출)이므로 답 무관 —
    PAIR.program 을 구체(literal)로 정직화. 예측/일반화는 TASK.solution 의 몫."""
    colorset = sorted({v for row in out for v in row})
    return (PA.const({"height": len(out), "width": len(out[0])}), PA.const(colorset))


def _assemble_pair_program(ag, code):
    """grid-skeleton 이 있으면 그 skeleton 을 pair 프로그램으로 조립: size/color 는 **그 pair 출력의
    리터럴 const**(예측·pending 아님)로, `set_grid_contents` pending 슬롯은 하강 coloring body(`code`)로
    감싼 grid body(3슬롯)를 PAIR.program 으로 반환. skeleton 없으면(순수 pixel 문제) `code` 그대로."""
    sk = _find_grid_skeleton(ag)
    if sk is None:
        return code
    gp = json.loads(sk)
    try:
        coloring_body = json.loads(code)["body"]
    except (ValueError, TypeError, KeyError):
        coloring_body = []                             # 하강 재채색 없었음(항등) → 빈 합성(=identity)
    k = pair_cursor(ag)
    size_leaf, color_leaf = _literal_grid_props(ag.task["train"][k]["output"])
    body = []
    for s in gp.get("body") or []:
        call = s.get("call")
        if call == "set_grid_size":
            s = PA.set_grid_size(size_leaf)            # per-pair 리터럴(pending/expr 대체)
        elif call == "set_grid_color":
            s = PA.set_grid_color(color_leaf)
        elif call == "set_grid_contents":
            leaf = (s.get("args") or {}).get("contents")
            if isinstance(leaf, dict) and "pending" in leaf:
                s = PA.set_grid_contents(PA.contents_program(coloring_body))
        body.append(s)
    return json.dumps(dict(gp, body=body))


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
                 "program-code", "base-program", "recolor-rel-pending"):
        for (i, a, v) in list(ag.wm.matching(identifier=sid, attr=attr)):
            drop(i, a, v)
    for (i, a, e) in list(ag.wm.matching(identifier=sid, attr="recolor-rel")):
        drop(i, a, e)             # sid→E edge 만 지움(E 자신은 compare 가 만든 relation — 안 건드림,
        #                           E ^colored yes 는 "이미 칠함" 사실이라 다음 pair 로도 유효해 유지)
