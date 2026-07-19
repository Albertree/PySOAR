# -*- coding: utf-8 -*-
"""ARBOR operator body: coloring (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning import program_ast as PA
from arbor.reasoning.program_ast import as_source


def _hop(ag, i, a):
    """WM 1-hop: (i,a,v) 의 v (없으면 None). relation nested cascade 를 걸어 내려갈 때 씀."""
    return next((v for (ii, aa, v) in ag.wm if ii == i and aa == a), None)


def _pixel_rel_cell(ag, E):
    """pixel compare relation(`{pair}.E_G0Xi-G1Xi`, category.color=DIFF·category.coordinate=COMM) 에서
    (r, cx, out) 를 뽑는다 — object relation(E_G0Oi-G1Oj) 은 category.coordinate 가 좌표리스트 통짜
    (comp1=list, row_index 경로 없음)라 여기서 None → 그걸로 pixel 판별(§brief 실측 구조)."""
    C = _hop(ag, E, "category")
    if C is None:
        return None
    col, crd = _hop(ag, C, "color"), _hop(ag, C, "coordinate")
    if col is None or crd is None:
        return None
    cc = _hop(ag, crd, "category")
    if cc is None:
        return None
    ri, ci = _hop(ag, cc, "row_index"), _hop(ag, cc, "col_index")
    if ri is None or ci is None:
        return None
    r, cx = int(_hop(ag, ri, "comp1")), int(_hop(ag, ci, "comp1"))
    out = int(_hop(ag, col, "comp2"))
    return (r, cx, out)


def _op_coloring_pixel_rel(ag, sid):
    """PIXEL 재채색 — xform 대신 이미 WM 에 있는 pixel compare relation(`sid ^recolor-rel E`)에서
    좌표·색을 읽어 칠한다(Part B: hypothesize 가 더는 xform 을 안 만듦). 미적용(`E ^colored yes` 아님)
    전부를 **한 번에** r*W+cx 오름차순(옛 xform g0idx=r*W+c 순과 동일 = byte-safe)으로 칠하고 program
    step 을 방출 — object 가설(`sid ^base-program`)에 이어붙임(object 가 먼저 칠한 뒤 잔여를 pixel 이 마감).
    처리한 relation 이 하나도 없으면(전부 object 소관) None 반환 → 호출부가 기존 xform 경로로 fallback."""
    from procedural_memory.dsl.transformation import coloring   # vendored
    rels = [E for (i, a, E) in ag.wm if i == sid and a == "recolor-rel"
            and not ag.wm.contains(E, "colored", "yes")]
    cells = [(E,) + cell for E in rels for cell in (_pixel_rel_cell(ag, E),) if cell is not None]
    if not cells:
        return None
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in sim]
    W = len(grid[0])
    cells.sort(key=lambda t: t[1] * W + t[2])          # r*W+cx 오름차순 — xform g0idx=r*W+c 와 동일 순서
    base_v = next((v for (i, a, v) in ag.wm if i == sid and a == "base-program"), None)
    base_ast = None
    if base_v:
        try:
            base_ast = json.loads(base_v) if base_v.lstrip().startswith("{") and "body" in json.loads(base_v) else None
        except (ValueError, TypeError):
            base_ast = None
    body = list(base_ast["body"]) if base_ast else []
    for (E, r, cx, out) in cells:
        if 0 <= r < len(grid) and 0 <= cx < len(grid[0]):
            grid = coloring(grid, (r, cx), out)          # frozen atom — 입력셀 → target 색
        body.append(PA.step("coloring", target=PA.ref("coord", PA.const([r, cx])), color=PA.const(out)))
        ag.wm.add(E, "colored", "yes")
    ast = PA.program(body)
    ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
    ag.wm.add(sid, "program-code", json.dumps(ast))
    ag.wm.add(sid, "colored-all", "yes")               # recolor 다 적용 → verify
    return True


def _op_coloring(ag):
    """**coloring DSL operator (apply body = 원자연산만)** — 첫 미적용 recolor xform 의 g0cells 를
    g1color 로 시뮬 grid 에 칠한다(procedural_memory.coloring, frozen). '무엇을/언제'는 **규칙**
    (propose*coloring: color DIFF ∧ coord COMM 인 xform 이 있을 때)이 정한다. 하나 칠하고 applied
    표시 → 남은 게 없으면 colored-all(→ verify)."""
    from procedural_memory.dsl.transformation import coloring   # vendored
    sid = ag.stack[-1].id
    if _op_coloring_pixel_rel(ag, sid):        # PIXEL: recolor-rel 이 있으면 relation 경로로 처리·종료
        return
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
