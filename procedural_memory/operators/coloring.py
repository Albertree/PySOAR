# -*- coding: utf-8 -*-
"""ARBOR operator body: coloring (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arbor.expr_solver import build_arckg, _load_value, _tup
from arbor.reasoning import program_ast as PA


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
    처리한 pixel relation 이 하나도 없으면(전부 object 소관) None 반환 → 호출부가 object relation 경로로 넘어감."""
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
    """**coloring DSL operator (apply body = 원자연산만)** — xform 없이 pixel compare relation 에서
    직접 읽어 칠한다(Part B). pixel recolor-rel 이 있으면 pixel 경로(`_op_coloring_pixel_rel`)로 처리,
    없으면 colored-all(→ verify). '무엇을/언제'는 **규칙**(propose*coloring: recolor-rel-pending 존재)이 정한다.

    (2026-07-19 원천차단) **object 재채색은 제거됨.** coloring 은 단일 position 을 받는데 object 는 셀 집합
    이라, object 좌표를 coloring 의 position arg 로 넣는 **규칙이 없다**. 예전엔 body 가 relation 의
    coordinate 리스트를 읽어 셀마다 frozen coloring 을 도는 **해킹**으로만 성립했으므로, 그 body 경로를
    아예 지워 object coloring 이 일어나지 못하게 한다. object compare relation 은 WM 에 descriptive 로만
    남는다(추후 좌표집합을 arg 로 공급하는 규칙 기반 메커니즘이 생기면 그때 소비)."""
    sid = ag.stack[-1].id
    if _op_coloring_pixel_rel(ag, sid):        # PIXEL: recolor-rel 이 있으면 relation 경로로 처리·종료
        return
    ag.wm.add(sid, "colored-all", "yes")
