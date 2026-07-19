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


def _g0_obj_idx(E):
    """object relation id(`...E_G0O{i}-G1O{j}`) 꼬리에서 i(int) 추출 — 처리 순서 결정용(오름차순,
    옛 xform order 와 동일한 결정적 순서 = byte-safe)."""
    tail = E.rsplit(".E_G0O", 1)[-1]            # "{i}-G1O{j}..."
    digits = tail.split("-", 1)[0]
    return int(digits) if digits.isdigit() else 0


def _op_coloring_object_rel(ag, sid):
    """OBJECT 재채색 — xform 대신 이미 WM 에 있는 object compare relation(`sid ^recolor-rel E`,
    E=`{pair}.E_G0Oi-G1Oj`)에서 대상 셀·색을 읽어 칠한다(Part B: xform 대체, Task2 의
    `_op_coloring_pixel_rel` 과 동형). object relation 의 `category.coordinate ^comp1` 은 좌표
    리스트 통짜(pixel 과 달리 row_index/col_index 중첩 없음 — 그래서 `_pixel_rel_cell` 이 None 반환,
    이걸로 pixel/object 를 구별한다 §brief 실측). objects_of(input) 성분 좌표집합과 맞춰 g0idx
    (program 의 in_objs[i] 참조)를 얻고, color 의 one-hot category 에서 comp2=True 인 첫 색을
    출력색으로 삼는다. E 의 G0 O-번호 오름차순으로 **한 번에** 처리(pixel 경로와 동일 모델).
    처리한 relation 이 하나도 없으면(전부 pixel 소관/이미 처리됨) None 반환."""
    from procedural_memory.dsl.transformation import coloring   # vendored
    from arbor.perception.perception import objects_of
    rels = [E for (i, a, E) in ag.wm if i == sid and a == "recolor-rel"
            and _pixel_rel_cell(ag, E) is None                  # pixel 아님(coordinate 가 좌표리스트)
            and not ag.wm.contains(E, "colored", "yes")]
    if not rels:
        return None
    rels.sort(key=_g0_obj_idx)
    sim = next((v for (i, a, v) in ag.wm if i == sid and a == "sim"), None)
    grid = [list(r) for r in sim]
    in_idx = {frozenset(c): k for k, (c, col) in enumerate(objects_of(grid))}   # program 의 in_objs[i]
    body = []
    for E in rels:
        cells = [tuple(c) for c in (_hop(ag, f"{E}.category.coordinate", "comp1") or ())]
        g0idx = in_idx.get(frozenset(cells))
        if g0idx is None:                          # 배경 등 objects_of 미매칭 → step 안 냄
            ag.wm.add(E, "colored", "yes"); continue
        colcat = f"{E}.category.color.category"
        out = next((k for k in range(10)
                    if _hop(ag, f"{colcat}.{k}", "comp2") in ("True", True)), None)
        if out is None:                            # comp2=True 인 색이 없음(방어적) → step 안 냄
            ag.wm.add(E, "colored", "yes"); continue
        for (r, c) in cells:                        # frozen coloring atom 으로 입력셀 → target색
            if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                grid = coloring(grid, (r, c), out)
        body.append(PA.step("coloring", target=PA.ref("object", PA.const(g0idx)), color=PA.const(out)))
        ag.wm.add(E, "colored", "yes")
    ag.wm.remove(sid, "sim", sim); ag.wm.add(sid, "sim", _tup(grid))
    ag.wm.add(sid, "program-code", json.dumps(PA.program(body)))
    ag.wm.add(sid, "colored-all", "yes")           # recolor 다 적용 → verify
    return True


def _op_coloring(ag):
    """**coloring DSL operator (apply body = 원자연산만)** — xform 없이 compare relation 에서 직접
    읽어 칠한다(Part B). pixel recolor-rel 이 있으면 pixel 경로(`_op_coloring_pixel_rel`), 없고
    object recolor-rel 이 있으면 object 경로(`_op_coloring_object_rel`) — 둘 다 미적용분을 **한 번에**
    처리. 어느 쪽도 없으면 colored-all(→ verify). '무엇을/언제'는 **규칙**(propose*coloring:
    recolor-rel-pending 존재)이 정한다."""
    sid = ag.stack[-1].id
    if _op_coloring_pixel_rel(ag, sid):        # PIXEL: recolor-rel 이 있으면 relation 경로로 처리·종료
        return
    if _op_coloring_object_rel(ag, sid):       # OBJECT: recolor-rel 이 있으면 relation 경로로 처리·종료
        return
    ag.wm.add(sid, "colored-all", "yes")
