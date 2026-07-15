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

from arbor.reasoning.antiunify import parse_program
from arbor.reasoning.program_ast import as_source


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


def _blob_program(code, W):
    """pixel program 문자열 → blob(object-level) program 문자열. 압축 불가(파싱 실패)면 None."""
    ops = parse_program(code)
    if not ops:
        return None
    blobs = _blobs(ops, W)
    blobs.sort(key=lambda b: b[0][0])                     # 첫 셀 순 (pair 간 정렬 안정)
    defs, steps = [], ["tfg0 = input_grid"]
    for j, (cells, col) in enumerate(blobs):
        idxs = [r * W + c for (r, c) in cells]
        defs.append(f"B{j} = {idxs}")
        steps.append(f"tfg{j + 1} = apply_DSL(tfg{j}, coloring, B{j}, {col})")
    steps.append(f"output_grid = tfg{len(blobs)}")
    return "\n".join(defs + [""] + steps)


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
        if not code or code == "{}":
            continue
        W = len(ag.task["train"][k]["input"][0])
        blob = _blob_program(code, W)
        if blob is None:
            continue
        ag.wm.remove(ppid, "program", raw)     # was: code
        ag.wm.add(ppid, "program", blob)                  # pixel → blob(객체) program
        n += 1
    for (i, a, v) in list(ag.wm.matching(identifier=sid, attr="needs-compress")):
        ag.wm.remove(i, a, v)                             # 신호 소거 → generalize 재발화 가능
    ag.wm.add(sid, "compressed", "yes")
    ag.kg["compress"] = {"n_pairs": n}
