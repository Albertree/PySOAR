# -*- coding: utf-8 -*-
"""ARBOR operator body: compress (program 내부 합성, procedural LTM leaf).

pixel 단위 pair.program 을 **seed+인접성장(region growing)** 으로 연결 덩어리(blob)로 묶어
object-level program 으로 축약한다. 덩어리 술어 = 4-인접 + 같은 목표색(전역 색묶음 아님 →
0ca9 식 오합체 방지; 연결성이 1차, 색은 그 위의 술어). 각 덩어리 = coloring 1회(실행 시
단일셀 coloring 조합 — coloring DSL 은 동결 유지). 이동처럼 객체 크기가 달라 pixel op 수가
pair 마다 달라 anti-unify 가 막혔을 때(generalize 가 needs-compress 로 신호), 덩어리화하면
두 program 이 같은 op 수 구조가 되어 정렬된다. 덩어리가 ARCKG object 와 맞으면 그게 근거.

일반적: pixel op 가 객체로 뭉치는 어떤 태스크에도 재발화(made000b 전용 아님).
"""
from __future__ import annotations

import json
from arbor.reasoning.antiunify import parse_program
from arbor.reasoning.program_ast import (as_source, program, step, cellset, const,
    set_grid_size, set_grid_color, set_grid_contents, contents_program)


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
        ops = [(t["args"]["target"]["index"]["const"], t["args"]["color"]["const"])
               for t in inner if t["args"]["target"].get("ref") == "pixel"]
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
    # ── 기존 flat pixel 경로 (변경 없음) ──
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
        idxs = [r * W + c for (r, c) in cells]
        body.append(step("coloring", target=cellset(const(idxs)), color=const(col)))
    return body if body else None


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
        blob = _blob_program(raw, W)               # raw AST-json 그대로 → grid 분기 도달(as_source 로 납작해지면 grid 탐지 불가)
        if blob is None:
            continue
        ag.wm.remove(ppid, "program", raw)     # was: code
        ag.wm.add(ppid, "program", blob)                  # pixel → blob(객체) program
        n += 1
    for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-compress")):
        ag.wm.remove(i, a, v)                             # 신호 소거 → generalize 재발화 가능
    ag.wm.add(sid, "compressed", "yes")
    ag.kg["compress"] = {"n_pairs": n}
