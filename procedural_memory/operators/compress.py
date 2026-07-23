# -*- coding: utf-8 -*-
"""ARBOR operator body: compress (program 내부 합성, procedural LTM leaf).

pixel 단위 pair.program 을 **seed+인접성장(region growing)** 으로 연결 덩어리(blob)로 묶어
object-level program 으로 축약한다. 덩어리 술어 = 4-인접 + 같은 목표색(전역 색묶음 아님 →
0ca9 식 오합체 방지; 연결성이 1차, 색은 그 위의 술어). 각 덩어리 = coloring 1회(실행 시
단일셀 coloring 조합 — coloring DSL 은 동결 유지). 이동처럼 객체 크기가 달라 pixel op 수가
pair 마다 달라 anti-unify 가 막혔을 때(generalize 가 needs-compress 로 신호), 덩어리화하면
두 program 이 같은 op 수 구조가 되어 정렬된다. 덩어리가 ARCKG object 와 맞으면 그게 근거.

일반적: pixel op 가 객체로 뭉치는 어떤 태스크에도 재발화(특정 태스크 전용 아님).
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import parse_program, _components
from arbor.reasoning.program_ast import (as_source, program, step, const, expr,
    grid_program, set_grid_size, set_grid_color, set_grid_contents, contents_program, ops_of_ast,
    coordinate_of, select, coord_in)


def _select_target(cells):
    """(r,c) 목록 → coordinate_of(select("input","pixel",coord_in(...))) target (cellset 동치, P2b)."""
    return coordinate_of(select("input", "pixel", coord_in("pixel_coordinate", [[r, c] for (r, c) in cells])))


def _blobs(cells_colored, W):
    """(idx,color) 목록 → 연결 덩어리 [(sorted cells, color)] (seed 하나서 4-인접·동색만 성장)."""
    pos = {(idx // W, idx % W): col for idx, col in cells_colored}
    seen, blobs = set(), []
    for start in pos:
        if start in seen:
            continue
        col, stack, cells = pos[start], [start], []
        while stack:
            y, x = stack.pop()
            if (y, x) in seen or pos.get((y, x)) != col:
                continue
            seen.add((y, x)); cells.append((y, x))
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
        blobs.append((sorted(cells), col))
    return blobs


def _blob_program(code, W, predicate="color"):
    """pixel program(AST-json|legacy) → blob(object-level) AST-json.
    grid>pixel 이면 inner contents 만 blob화하고 size/color leaf 보존. 압축 불가면 None."""
    from arbor.reasoning.program_ast import _is_grid_body
    try:
        ast = json.loads(code) if code and code.lstrip().startswith("{") else None
    except (ValueError, TypeError):
        ast = None
    if ast and _is_grid_body(ast.get("body") or []):
        parts = {s["call"]: s["args"] for s in ast["body"]}
        cleaf = parts["set_grid_contents"]["contents"]
        inner = (cleaf.get("program") or {}).get("body") if "program" in cleaf else None
        if not inner:
            return None
        W_ = W
        ops = []
        for t in inner:
            tg = t["args"]["target"]
            if tg.get("ref") == "pixel":
                ops.append((tg["index"]["const"], t["args"]["color"]["const"]))
            elif tg.get("ref") == "coord":
                r_, c_ = tg["index"]["const"]
                ops.append((r_ * W_ + c_, t["args"]["color"]["const"]))
        if len(ops) != len(inner):
            return None
        blob_body = _blob_body(ops, W, predicate)
        if blob_body is None:
            return None
        new = dict(parts)
        new_contents = set_grid_contents(contents_program(blob_body))
        body = [set_grid_size(parts["set_grid_size"]["size"]),
                set_grid_color(parts["set_grid_color"]["color"]),
                new_contents]
        return json.dumps(program(body))
    # ── flat(non-grid) pixel/coord 경로 — AST 에서 직접 ops 도출(coord-aware) ──
    # Task4 이후 pixel coloring 은 ref("coord",[r,c]) 리터럴로도 emit 된다. 이걸 as_source 로 렌더하면
    # 문자열 `apply_DSL(tfg,coloring,(r,c),color)` 가 되어 parse_program 의 _STEP 정규식(VAR.coord 만
    # 인식)이 못 잡는다(§finding). ops_of_ast 는 AST 를 직접 읽으므로 pixel(idx)·coord((r,c)) 둘 다
    # 정직하게 (target,color) 로 낸다 — 문자열 재렌더(정보손실)를 거치지 않는다.
    if ast and ast.get("body"):
        raw_ops = ops_of_ast(ast)
        ops = []
        for tgt, col in raw_ops:
            if tgt is None or col is None:
                return None                          # 미결정 slot 포함 → 압축 불가(기존 parse_program 동치)
            if isinstance(tgt, tuple):                # coord (r,c) 리터럴 → 픽셀 인덱스로 접기(_blob_body 계약)
                r_, c_ = tgt
                tgt = r_ * W + c_
            elif not isinstance(tgt, int):            # cellset(frozenset) 등 이미-blob 형은 이 경로 대상 아님
                return None
            ops.append((tgt, col))
        blob_body = _blob_body(ops, W, predicate)
        return json.dumps(program(blob_body)) if blob_body else None
    # ── legacy fallback: 진짜 비-JSON(구 flat 텍스트) 입력만. 정상 AST-json 은 위 분기가 처리한다. ──
    ops = parse_program(as_source(code))
    if not ops:
        return None
    blob_body = _blob_body(ops, W, predicate)
    return json.dumps(program(blob_body)) if blob_body else None


def _blob_body(ops, W, predicate="color"):
    """(idx,color) 목록 → blob step 리스트. Task 4 에서 predicate 분기; 여기선 color(연결성) 기본."""
    blobs = _blobs(ops, W)
    blobs.sort(key=lambda b: b[0][0])
    body = []
    for (cells, col) in blobs:
        body.append(step("coloring", target=_select_target(cells), color=const(col)))
    return body if body else None


# ── 대응 기반 전체-객체 이동 (잔여가 아니라 objects_of 로 복원 → 겹침에도 정확) ─────────────
# 잔여(residual) blobify 는 객체가 원위치와 겹치면 비운 셀 일부만 남아 객체 정체성을 잃는다(모양 불일치).
# 대신 G0/G1 의 성분(_components=objects_of)을 대응(같은 모양·색·다른 위치)해 **전체 객체** 를 잡고,
# erase(전체 C_O → 비운색) + paint(전체 C_O' → 객체색) 로 표현한다. 겹침 셀은 erase 후 paint 로 복원.
def _norm_shape(cells):
    rs = min(r for r, _ in cells); cs = min(c for _, c in cells)
    return frozenset((r - rs, c - cs) for r, c in cells)


def _object_moves(g0, g1):
    """G0→G1 이동 객체쌍 [(cells0, cells1, color)] — 같은 모양·색, 다른 위치. 배경은 이동 시 모양이
    달라져 자기매칭 안 됨(그래서 '배경=0' 가정 없이 성분 전부 대응해도 안전).
    **static 우선**: 같은 위치·색·모양 성분을 먼저 예약(제자리 유지)한 뒤 남은 것에서만 이동을 찾는다.
    안 그러면 배경색 조각(색0 1칸 등)이 사라진 자리↔제자리 조각과 greedy 매칭돼 phantom 이동으로 오탐
    (예: move000aq 에서 한 pair 만 이동 2개로 세어져 op 수 불일치→anti-unify 실패)."""
    o0, o1 = _components(g0), _components(g1)
    used, matched0 = set(), set()
    for i, (cells0, col0) in enumerate(o0):                   # 1st: static(같은 위치) 예약 → mover 오탐 방지
        s0 = sorted(cells0)
        for j, (cells1, col1) in enumerate(o1):
            if j in used or col1 != col0:
                continue
            if sorted(cells1) == s0:                           # 같은 위치·색 = 제자리(static)
                used.add(j); matched0.add(i); break
    moves = []
    for i, (cells0, col0) in enumerate(o0):                   # 2nd: 남은 것에서만 같은 모양·색·다른 위치 = 이동
        if i in matched0:
            continue
        s0 = _norm_shape(cells0)
        for j, (cells1, col1) in enumerate(o1):
            if j in used or col1 != col0:
                continue
            if _norm_shape(cells1) == s0 and sorted(cells1) != sorted(cells0):
                used.add(j); moves.append((sorted(cells0), sorted(cells1), col0)); break
    return moves


def _object_changes(g0, g1):
    """G0→G1 **대응 객체의 변화** 목록 [(cells0, cells1, col0, col1, kind)] — 이동/재채색 통합.
    원리: '변화가 있는 두 객체를 매핑'(구조 대응) → 차이를 프로그램으로 메운다. move/recolor 를
    특수조건으로 분기하지 않고, 대응 후 **무엇이 달라졌나**(위치·색)로 kind 를 도출한다.
    static(같은 위치·색) 먼저 예약(변화 아님) → 남은 것에서:
      · 같은 위치, 색 다름              = recolor
      · 같은 모양·색, 위치 다름          = move
      · 같은 모양, 위치·색 다름          = move (erase+paint 로 색까지 반영)
    대응 못 한 성분이 남으면 [] (compress 부적합 → 호출측 fallback)."""
    o0, o1 = _components(g0), _components(g1)
    used, static0, changes = set(), set(), []
    for i, (c0, col0) in enumerate(o0):                       # 1st: static(같은 위치·색) 예약 → 변화 오탐 방지
        s0 = sorted(c0)
        for j, (c1, col1) in enumerate(o1):
            if j in used or col1 != col0:
                continue
            if sorted(c1) == s0:
                used.add(j); static0.add(i); break
    for i, (c0, col0) in enumerate(o0):                       # 2nd: recolor(같은 위치, 색 다름)
        if i in static0:
            continue
        s0 = sorted(c0)
        for j, (c1, col1) in enumerate(o1):
            if j in used or sorted(c1) != s0:
                continue
            used.add(j); static0.add(i)
            changes.append((sorted(c0), sorted(c1), col0, col1, "recolor")); break
    for i, (c0, col0) in enumerate(o0):                       # 3rd: move(같은 모양, 위치 다름; 색은 erase+paint 로)
        if i in static0:
            continue
        s0 = _norm_shape(c0)
        for j, (c1, col1) in enumerate(o1):
            if j in used or _norm_shape(c1) != s0 or sorted(c1) == sorted(c0):
                continue
            used.add(j)
            changes.append((sorted(c0), sorted(c1), col0, col1, "move")); break
    return changes


def _object_moves(g0, g1):
    """하위호환 alias — 이동(move)만 (cells0, cells1, color)."""
    return [(c0, c1, col0) for (c0, c1, col0, col1, k) in _object_changes(g0, g1) if k == "move"]


def _object_change_program(g0, g1, W):
    """**대응 객체의 차이**(위치·색) → grid>blob program. 변화 없으면 None. size/color KEEP.
      · recolor: 그 객체 셀 전체를 새 색으로 (제자리 재채색)
      · move   : erase(원 셀 → 비운색) + paint(새 위치 셀 → 새 색)"""
    changes = _object_changes(g0, g1)
    if not changes:
        return None
    body = []
    for cells0, cells1, col0, col1, kind in changes:
        if kind == "recolor":                                # 제자리 재채색 = 객체 셀 → 새 색
            body.append(step("coloring", target=_select_target(cells0), color=const(col1)))
            continue
        set1 = set(cells1)                                   # move: erase 후 paint(색까지 반영)
        vac = [(r, c) for (r, c) in cells0 if (r, c) not in set1]
        if vac:
            vr, vc = vac[0]
            body.append(step("coloring", target=_select_target(cells0), color=const(g1[vr][vc])))
        body.append(step("coloring", target=_select_target(cells1), color=const(col1)))
    gp = grid_program(expr("size(input_grid)"), expr("color(input_grid)"), contents_program(body))
    return json.dumps(gp)


def _object_move_program(g0, g1, W):
    """하위호환 alias — 일반형(_object_change_program)으로 위임(이동·재채색 통합)."""
    return _object_change_program(g0, g1, W)


def _op_compress(ag):
    """**compress operator (apply body)** — 각 example-pair 의 pixel program 을 blob program 으로 재작성.
    이후 needs-compress 를 걷고 compressed 표시 → generalize 가 재발화해 blob 을 anti-unify 한다."""
    sid = ag.stack[-1].id
    root = ag.kg.get("arckg_root")
    if root is None:
        ag.wm.add(sid, "compressed", "failed")
        return
    pairs = list(getattr(root, "example_pairs", []) or [])
    n = 0
    for k, p in enumerate(pairs):
        if k >= len(ag.task["train"]):
            break
        ppid = f"{p.node_id}.property"
        raw = next((v for (i, a, v) in ag.wm if i == ppid and a == "program"), None)
        code = as_source(raw)
        if not code or code == "{}":               # emptiness guard만 flat 로 (미합성 sentinel 스킵)
            continue
        W = len(ag.task["train"][k]["input"][0])
        g0, g1 = ag.task["train"][k]["input"], ag.task["train"][k].get("output")
        blob = _object_move_program(g0, g1, W) if g1 is not None else None  # 대응 기반 전체-객체 우선(겹침 견고)
        if blob is None:
            blob = _blob_program(raw, W)           # 잔여 blobify fallback (raw AST-json → grid 분기 도달)
        if blob is None:
            continue
        ag.wm.add(ppid, "grouping", blob)                 # 객체 grouping = 별도 아티팩트(PAIR.program 픽셀 유지)
        n += 1
    for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-compress")):
        ag.wm.remove(i, a, v)                             # 신호 소거 → generalize 재발화 가능
    ag.wm.add(sid, "compressed", "yes")
    ag.kg["compress"] = {"n_pairs": n}
