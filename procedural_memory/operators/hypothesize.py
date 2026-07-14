# -*- coding: utf-8 -*-
"""ARBOR operator body: hypothesize (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.perception.perception import _fg_correspondence, _obj_cc, objects_of
from procedural_memory.operators.coloring import _recolor_pending


def _op_hypothesize(ag):
    """**hypothesize = 시뮬레이션 open** (조립·검증은 규칙이!). object mapping 대응을 얻어,
    각 대응쌍을 **변환 후보(xform)** 로 WM 에 노출한다 — 속성별 COMM/DIFF 를 그대로 실어(규칙이
    'color DIFF ∧ coordinate COMM → coloring' 을 판단). 시뮬 grid 를 G0(input)로 초기화.
    조립은 이후 coloring operator(규칙 propose/apply)가, 검증은 verify operator 가 한다.
    (여기 body 는 '지각'만 — 대응/COMM-DIFF 노출 + 시뮬 초기화. 조립 로직은 Python 아님·규칙.)"""
    idx, sid = ag.kg["idx"], ag.stack[-1].id
    root = ag.kg["arckg_root"]
    p0 = root.example_pairs[0]
    gid0, gid1 = p0.input_grid.node_id, p0.output_grid.node_id
    ag.wm.add(sid, "sim-pair", p0.node_id)

    g0grid = [list(r) for r in ag.task["train"][0]["input"]]
    g1grid = [list(r) for r in ag.task["train"][0]["output"]]
    if ag.wm.contains(sid, "level", "GRID"):
        # ── GRID hypothesize = **별도 가설공간(H-space) 열기**. 실제 가설 조합·검증은 그 공간 안에서
        #    `synthesize` DSL operator 가 SOAR 사이클로 수행(사용자 2026-07-13). 여기선 공간만 연다.
        ag.create_hspace(ag.stack[-1], "GRID")
        return
    if ag.wm.contains(sid, "level", "PIXEL"):
        # PIXEL 가설 = **잔여(residual) 처리**: 상위(object) substate 가 재채색한 sim·program 을 이어받아,
        # object 로 못 맞춘 셀(그 sim 이 아직 G1 과 다른 셀)만 pixel 로 재채색해 **object 가설에 덧붙인다**.
        # object 로 완결된 문제(845·868·08ed)는 애초에 PIXEL 로 안 내려온다(object verify 통과). object 가
        # 일부만 처리한 문제(예: 009d5c81)는 그 sim 에서 이어받아 잔여만 pixel 이 마감한다.
        sup = ag.stack[-2].id if len(ag.stack) >= 2 else None
        base_sim = next((v for (i, a, v) in ag.wm if i == sup and a == "sim"), None) if sup else None
        base_prog = next((v for (i, a, v) in ag.wm if i == sup and a == "program-code"), None) if sup else None
        sim0 = [list(r) for r in base_sim] if base_sim else [list(r) for r in g0grid]  # object 재채색 후 상태
        ag.wm.add(sid, "sim", _tup(sim0))                       # pixel sim = object 재채색 결과에서 이어감
        if base_prog:
            ag.wm.add(sid, "base-program", base_prog)           # 덧붙일 object 가설(program)
        # 잔여: object 재채색 후에도 G1 과 다른 셀만. object xform 과 같은 WME 형태(diff=color·comm=coordinate·
        # g0cells·g1color, +px)라 아래 coloring/verify 규칙을 그대로 탄다. g0idx=r*W+c=pixels_of(input)[i].
        # 같은 크기일 때만 셀 단위 재채색 가능(크기변화 → xform 없이 verify 실패 = 정직).
        H0, W0, H1, W1 = len(sim0), len(sim0[0]), len(g1grid), len(g1grid[0])
        W = W0; order = 0
        for r in range(H0 if (H0, W0) == (H1, W1) else 0):
            for c in range(W):
                if sim0[r][c] != g1grid[r][c]:                  # 잔여 변화 셀 = color DIFF ∧ coord COMM
                    xid = f"{sid}.xform.{order}"
                    ag.wm.add(sid, "xform", xid); ag.wm.add(xid, "px", "yes")
                    ag.wm.add(xid, "order", str(order))
                    ag.wm.add(xid, "diff", "color"); ag.wm.add(xid, "comm", "coordinate")
                    ag.wm.add(xid, "g0cells", _tup([[r, c]]))    # 단일 셀 (pixel)
                    ag.wm.add(xid, "g1color", str(g1grid[r][c]))  # 그 셀의 출력 색
                    ag.wm.add(xid, "g0idx", str(r * W + c))       # pixels_of(input)[i]
                    order += 1
    else:
        ag.wm.add(sid, "sim", _tup(g0grid))                     # OBJECT: 시뮬 grid = G0
        # OBJECT 가설: object mapping 대응 → xform (objects_of[i] 참조). in_idx/out_idx 는 program 참조용.
        in_idx = {frozenset(c): k for k, (c, col) in enumerate(objects_of(g0grid))}   # program 의 in_objs[i]
        order = 0
        for a, b, cat in _fg_correspondence(ag, gid0, gid1, g0grid, g1grid):   # 대응쌍 → 변환 후보 노출
            xid = f"{sid}.xform.{order}"
            ag.wm.add(sid, "xform", xid); ag.wm.add(xid, "order", str(order))
            for prop, v in cat.items():                            # 속성별 COMM/DIFF (규칙이 매칭)
                t = v.get("type") if isinstance(v, dict) else v
                if t in ("COMM", "DIFF"):
                    ag.wm.add(xid, t.lower(), prop)                # (xid ^diff color)(xid ^comm coordinate)…
            (g0cells, _), (_, g1color) = _obj_cc(idx["nodes"][a]), _obj_cc(idx["nodes"][b])
            ag.wm.add(xid, "g0cells", _tup([list(c) for c in g0cells]))   # 입력 객체 좌표(색칠 대상)
            ag.wm.add(xid, "g1color", str(g1color))                       # 출력 객체 색(칠할 색)
            ag.wm.add(xid, "g0idx", str(in_idx.get(frozenset(g0cells), 0)))    # objects_of(input)[i] 참조
            order += 1
    if _recolor_pending(ag, sid):              # 재채색(color DIFF ∧ coord COMM) 후보 있으면
        ag.wm.add(sid, "has-recolor", "yes")   # coloring 규칙 한 번만 발화(TIE 방지) — body 가 하나씩
    else:
        ag.wm.add(sid, "colored-all", "yes")   # 없으면 곧장 verify (시뮬=G0, 대개 실패 → PIXEL)
