# -*- coding: utf-8 -*-
"""ARBOR operator body: coloring (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning import program_ast as PA
from arbor.reasoning.program_ast import as_source


def _op_coloring(ag):
    """**coloring DSL operator (apply body = 원자연산만)** — 첫 미적용 recolor xform 의 g0cells 를
    g1color 로 시뮬 grid 에 칠한다(procedural_memory.coloring, frozen). '무엇을/언제'는 **규칙**
    (propose*coloring: color DIFF ∧ coord COMM 인 xform 이 있을 때)이 정한다. 하나 칠하고 applied
    표시 → 남은 게 없으면 colored-all(→ verify)."""
    from procedural_memory.dsl.transformation import coloring   # vendored
    sid = ag.stack[-1].id
    pend = _recolor_pending(ag, sid)
    if not pend:
        ag.wm.add(sid, "colored-all", "yes"); return
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in sim]

    def _wx(xid, attr):
        return next((v for (i, a, v) in ag.wm if i == xid and a == attr), None)
    # level-1 형식: 선택은 **objects_of(input)[i].coord**(OBJECT) / **pixels_of(input)[i].coord**(PIXEL) —
    # 실제 ARCKG 성분/픽셀 참조(provenance), 색은 target literal. PIXEL 이면 셀 단위(pixels_of[i]=r*W+c 번째 셀).
    order = sorted(pend, key=lambda x: int(_wx(x, "order") or "0"))
    px = bool(order) and ag.wm.contains(order[0], "px", "yes")
    base_v = next((v for (i, a, v) in ag.wm if i == sid and a == "base-program"), None) if px else None
    base_ast = None
    if base_v:
        bv = as_source(base_v)                      # 항상 flat; base 가 이미 AST 면 to_source
        # base 를 AST 로 되읽기: base_v 가 AST-json 이면 그대로, 아니면 legacy → 파싱 불가 시 steps 재구성
        try:
            base_ast = json.loads(base_v) if base_v.lstrip().startswith("{") and "body" in json.loads(base_v) else None
        except (ValueError, TypeError):
            base_ast = None
    level = "pixel" if px else "object"
    body = list(base_ast["body"]) if base_ast else []
    for xid in order:
        g0c = [tuple(c) for c in (_wx(xid, "g0cells") or ())]; g1col = int(_wx(xid, "g1color") or 0)
        g0i = int(_wx(xid, "g0idx") or 0)
        for (r, c) in g0c:                                     # frozen coloring atom 으로 입력셀 → target색
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                grid = coloring(grid, (r, c), g1col)
        ag.wm.add(xid, "applied", "yes")
        if level == "pixel":
            (rr, cc) = g0c[0]
            body.append(PA.step("coloring", target=PA.ref("coord", PA.const([rr, cc])), color=PA.const(g1col)))
        else:
            body.append(PA.step("coloring", target=PA.ref(level, PA.const(g0i)), color=PA.const(g1col)))
    ast = PA.program(body)
    ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
    ag.wm.add(sid, "program-code", json.dumps(ast))
    ag.wm.add(sid, "colored-all", "yes")                       # recolor 다 적용 → verify


def _recolor_pending(ag, sid):
    """미적용 recolor xform(color DIFF ∧ coordinate COMM)이 남아 있나 — coloring 규칙의 조건."""
    return [x for (i, a, x) in ag.wm if i == sid and a == "xform"
            and ag.wm.contains(x, "diff", "color") and ag.wm.contains(x, "comm", "coordinate")
            and not ag.wm.contains(x, "applied", "yes")]
