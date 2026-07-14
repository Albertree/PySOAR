# -*- coding: utf-8 -*-
"""ARBOR reasoning.antiunify — per-pair program 을 anti-unify 해 TASK.solution 골격+변수 도출.

하네스 §0.5/§2-3: anti-unification = 정렬된 per-pair program 들을 공통 골격 + 변수 스키마로
일반화. 실체 = compare(prog,prog) + DIFF slot 변수화. 정렬(structure mapping)이 선행조건이라,
program 들의 연산을 **COMM 최대화 순열**로 맞춘 뒤 비교한다(0=bg 가정 없이, §no-arbitrary-filters).
resolve(변수→G0 유래 식)는 **train pair 로만** 검증(§1-3/§4-1, test 오라클 금지 §P5).

program 포맷(coloring.py 생성, level-1 flat): P{i}=in_px[idx]; tfg=apply_DSL(...,P{i}.coord,color).
op i = (pixel_index, color). 내부 표현 skeleton={'ops':[(idx|None, color|None)]}.
"""
from __future__ import annotations

import itertools
import re

_DEF = re.compile(r"^\s*(\w+)\s*=\s*in_px\[(\d+)\]\s*$")
_STEP = re.compile(r"apply_DSL\([^,]+,\s*coloring,\s*(\w+)\.coord,\s*(\d+)\)")


def parse_program(code: str):
    """flat program → ops=[(pixel_index, color)] (step 순서). 파싱 불가면 None."""
    if not code or code.strip() in ("{}", ""):
        return None
    idx_of, steps = {}, []
    for ln in code.splitlines():
        m = _DEF.match(ln)
        if m:
            idx_of[m.group(1)] = int(m.group(2))
            continue
        m = _STEP.search(ln)
        if m:
            steps.append((m.group(1), int(m.group(2))))
    ops = [(idx_of.get(v), int(col)) for v, col in steps]
    if not ops or any(o[0] is None for o in ops):
        return None
    return ops


def _align(ref, ops):
    """ops 를 ref 에 **COMM(idx·color 일치) 최대화**하는 순열로 정렬 (structure mapping).
    연산 수가 작을 때만(≤6) 전수; 크면 원순서."""
    n = len(ref)
    if n > 6:
        return ops
    best, bestscore = ops, -1
    for perm in itertools.permutations(ops):
        score = sum((perm[i][0] == ref[i][0]) + (perm[i][1] == ref[i][1]) for i in range(n))
        if score > bestscore:
            bestscore, best = score, list(perm)
    return best


def antiunify(programs):
    """per-pair program 문자열들 → (skeleton, slots).
    skeleton={'ops':[(idx|None, color|None)]}; slots={name:{kind:'src'|'color', pos, values:[per-pair]}}.
    정렬 후 위치별 COMM=상수, DIFF=변수. 파싱/구조 불일치 시 (None, None)."""
    progs = [parse_program(p) for p in programs]
    progs = [p for p in progs if p]
    if len(progs) < 2:
        return None, None
    n = len(progs[0])
    if any(len(p) != n for p in progs):
        return None, None                       # 연산 수 다르면 이 골격으론 불가
    ref = progs[0]
    aligned = [ref] + [_align(ref, p) for p in progs[1:]]
    ops, slots = [], {}
    for i in range(n):
        idxs = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_idx = idxs[0] if len(set(idxs)) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        if sk_idx is None:
            slots[f"?src{i}"] = {"kind": "src", "pos": i, "values": idxs}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        ops.append((sk_idx, sk_col))
    return {"ops": ops}, slots


# ── resolve: 변수 slot → G0 유래 표현식 (generate → train 적용 → 대조 → 생존) ──────
def _fg_index(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v:
                return r * len(row) + c
    return None


def _fg_color(grid):
    for row in grid:
        for v in row:
            if v:
                return v
    return None


def _fg_coord(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v:
                return (r, c)
    return None


def _axis_cands(kind):
    """한 축(row 'r' / col 'c')의 후보식: {const, base, base±d, H-1/W-1}. (§4-1 좌표식 탐색.)
    fn(r0, c0, H, W) -> 좌표 성분."""
    base = (lambda r0, c0, H, W: r0) if kind == "r" else (lambda r0, c0, H, W: c0)
    bn = "r0" if kind == "r" else "c0"
    cands = [(f"const {k}", (lambda r0, c0, H, W, k=k: k)) for k in range(0, 10)]
    cands.append((bn, base))
    for d in (1, 2, 3):
        cands.append((f"{bn}+{d}", lambda r0, c0, H, W, d=d, b=base: b(r0, c0, H, W) + d))
        cands.append((f"{bn}-{d}", lambda r0, c0, H, W, d=d, b=base: b(r0, c0, H, W) - d))
    cands.append(("H-1" if kind == "r" else "W-1",
                  (lambda r0, c0, H, W: H - 1) if kind == "r" else (lambda r0, c0, H, W: W - 1)))
    return cands


def _coord_index_fn(rf, cf):
    """(row식, col식) → fn(grid): grid 의 fg 좌표·dims 로 픽셀 인덱스(row*W+col) 계산."""
    def fn(g):
        fc = _fg_coord(g)
        if fc is None:
            return None
        r0, c0 = fc
        H, W = len(g), len(g[0])
        return rf(r0, c0, H, W) * W + cf(r0, c0, H, W)
    return fn


def resolve_slot(slot, train):
    """slot(kind='src'|'color') → (survivors=[(name, fn)], tried=[(name, ok)]).
    src(픽셀 인덱스): fg_index 또는 좌표식(row*W+col) 탐색. color: color_of_fg. train 으로만 검증(§P5)."""
    vals = slot["values"]
    N = len(vals)
    if slot["kind"] == "color":
        cands = [("color_of_fg", _fg_color)]
        cands += [(f"const {k}", (lambda g, k=k: k)) for k in sorted(set(vals))]
        tried, survivors = [], []
        for name, fn in cands:
            ok = N == len(train) and all(fn(train[i]["input"]) == vals[i] for i in range(N))
            tried.append((name, ok))
            if ok:
                survivors.append((name, fn))
        return survivors, tried

    # --- src / 픽셀 인덱스 slot ---
    tried, survivors = [], []
    ok = N == len(train) and all(_fg_index(train[i]["input"]) == vals[i] for i in range(N))
    tried.append(("fg_index", ok))
    if ok:
        survivors.append(("fg_index", _fg_index))
    # 좌표 분해 후 축별 표현식 탐색 (상대이동·코너 등; §4-1 손계산 금지)
    per = []
    for i in range(N):
        g = train[i]["input"]
        fc = _fg_coord(g)
        if fc is None:
            per = None
            break
        r0, c0 = fc
        H, W = len(g), len(g[0])
        per.append((r0, c0, H, W, vals[i] // W, vals[i] % W))
    if per:
        for rn, rf in _axis_cands("r"):
            if not all(rf(p[0], p[1], p[2], p[3]) == p[4] for p in per):
                continue
            for cn, cf in _axis_cands("c"):
                if not all(cf(p[0], p[1], p[2], p[3]) == p[5] for p in per):
                    continue
                name = f"({rn},{cn})"
                survivors.append((name, _coord_index_fn(rf, cf)))
                tried.append((name, True))
    return survivors, tried


# ── 실행 + version space ─────────────────────────────────────────────────────
def solution_candidates(sol, limit=3):
    """resolved version space 곱 → [(label, choice{name:fn})] (≤limit; few-shot 애매성=3-attempt)."""
    slots, resolved = sol["slots"], sol.get("resolved") or {}
    names = list(slots.keys())
    if not names:
        return [("(변수 없음)", {})]
    pools = [resolved.get(n) or [] for n in names]
    if any(not pool for pool in pools):
        return []
    out = []
    for combo in itertools.product(*pools):
        choice = {names[i]: combo[i][1] for i in range(len(names))}
        label = ", ".join(f"{names[i]}={combo[i][0]}" for i in range(len(names)))
        out.append((label, choice))
        if len(out) >= limit:
            break
    return out


def execute_solution(skeleton, slots, choice, grid_in):
    """skeleton + slot별 선택 fn → grid_in 실행 → 답 격자."""
    H, W = len(grid_in), len(grid_in[0])
    src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
    col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
    grid = [list(r) for r in grid_in]
    for i, (idx, col) in enumerate(skeleton["ops"]):
        ix = idx if idx is not None else choice[src_at[i]](grid_in)
        c = col if col is not None else choice[col_at[i]](grid_in)
        if ix is None:
            continue
        r, cc = ix // W, ix % W
        if 0 <= r < H and 0 <= cc < W:
            grid[r][cc] = c
    return grid


def render_skeleton(skeleton, slots) -> str:
    """골격+변수 → TASK.solution 문자열(대시보드·저장)."""
    if not skeleton:
        return "{}"
    src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
    col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
    lines = ["in_px = pixels_of(input_grid)"]
    for i, (idx, col) in enumerate(skeleton["ops"]):
        ix = str(idx) if idx is not None else src_at[i]
        lines.append(f"P{i} = in_px[{ix}]")
    lines.append("")
    lines.append("tfg0 = input_grid")
    for i, (idx, col) in enumerate(skeleton["ops"]):
        c = str(col) if col is not None else col_at[i]
        lines.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, P{i}.coord, {c})")
    lines.append(f"output_grid = tfg{len(skeleton['ops'])}")
    return "\n".join(lines)
