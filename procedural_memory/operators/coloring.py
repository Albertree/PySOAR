# -*- coding: utf-8 -*-
"""ARBOR operator body: coloring (procedural LTM leaf). focus_solver 분리."""
from __future__ import annotations
import json, os, sys
from collections import Counter
from soar import Agent, Cond, Action, Production
from arc.expr_solver import build_arckg, _load_value, _tup


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
    base = next((v for (i, a, v) in ag.wm if i == sid and a == "base-program"), None) if px else None
    src, ref, var = (("in_px = pixels_of(input_grid)", "in_px", "P") if px
                     else ("in_objs = objects_of(input_grid)", "in_objs", "O"))
    if base:
        # PIXEL 잔여를 **object 가설(base)에 덧붙인다**: base 의 output_grid 라인만 떼고 tfg 번호를 이어감.
        # in_px·P{k} defs 를 base 뒤에 두고(사용 전 정의됨) 잔여 tfg step 을 tfgK 부터 계속.
        blines = [ln for ln in base.split("\n") if not ln.strip().startswith("output_grid")]
        base_n = int(base.rsplit("output_grid = tfg", 1)[-1].strip()) if "output_grid = tfg" in base else 0
        defs, steps = blines + [src], []
    else:
        defs, steps, base_n = [src], ["tfg0 = input_grid"], 0
    for k, xid in enumerate(order):
        g0c = [tuple(c) for c in (_wx(xid, "g0cells") or ())]; g1col = int(_wx(xid, "g1color") or 0)
        g0i = int(_wx(xid, "g0idx") or 0)
        for (r, c) in g0c:                                     # frozen coloring atom 으로 입력셀 → target색
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                grid = coloring(grid, (r, c), g1col)
        ag.wm.add(xid, "applied", "yes")
        defs.append(f"{var}{k} = {ref}[{g0i}]")               # 입력 성분/픽셀 참조 ([i])
        steps.append(f"tfg{base_n+k+1} = apply_DSL(tfg{base_n+k}, coloring, {var}{k}.coord, {g1col})")  # .coord → 색
    steps.append(f"output_grid = tfg{base_n + len(order)}")
    ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
    ag.wm.add(sid, "program-code", "\n".join(defs + [""] + steps))
    ag.wm.add(sid, "colored-all", "yes")                       # recolor 다 적용 → verify


def _recolor_pending(ag, sid):
    """미적용 recolor xform(color DIFF ∧ coordinate COMM)이 남아 있나 — coloring 규칙의 조건."""
    return [x for (i, a, x) in ag.wm if i == sid and a == "xform"
            and ag.wm.contains(x, "diff", "color") and ag.wm.contains(x, "comm", "coordinate")
            and not ag.wm.contains(x, "applied", "yes")]
