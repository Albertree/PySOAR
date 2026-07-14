# -*- coding: utf-8 -*-
"""ARBOR reasoning.antiunify — per-pair program 을 anti-unify 해 TASK.solution 골격+변수 도출.

하네스 §0.5/§2-3: anti-unification = 정렬된 per-pair program 들을 공통 골격 + 변수 스키마로
일반화. 실체 = compare(prog, prog) + DIFF slot 변수화. resolve(변수→G0 유래 표현식)는 이 파일의
탐색부에서 train pair 로만 검증(§1-3, test 오라클 금지).

program 포맷(coloring.py 가 생성, level-1 flat):
    in_px = pixels_of(input_grid)
    P0 = in_px[7]
    P1 = in_px[35]
    tfg0 = input_grid
    tfg1 = apply_DSL(tfg0, coloring, P0.coord, 0)
    tfg2 = apply_DSL(tfg1, coloring, P1.coord, 2)
    output_grid = tfg2
"""
from __future__ import annotations

import re

_DEF = re.compile(r"^\s*(\w+)\s*=\s*in_px\[(\d+)\]\s*$")
_STEP = re.compile(r"apply_DSL\([^,]+,\s*coloring,\s*(\w+)\.coord,\s*(\d+)\)")


def parse_program(code: str):
    """flat program 문자열 → {'defs': [(var, px_index)], 'steps': [(var, color)]}.
    파싱 불가(공백 '{}' 등)면 None."""
    if not code or code.strip() in ("{}", ""):
        return None
    defs, steps = [], []
    for ln in code.splitlines():
        m = _DEF.match(ln)
        if m:
            defs.append((m.group(1), int(m.group(2))))
            continue
        m = _STEP.search(ln)
        if m:
            steps.append((m.group(1), int(m.group(2))))
    if not steps:
        return None
    return {"defs": defs, "steps": steps}


def antiunify(programs: list[str]):
    """per-pair program 문자열들 → (skeleton, slots).

    같은 구조(같은 def/step 개수)의 program 들을 위치별로 compare:
      - 모든 pair 에서 같은 값 = COMM → 상수로 골격에 고정
      - 다른 값 = DIFF → 변수 slot (per-pair 값 목록 = 근거)

    반환:
      skeleton = {'defs': [(var, index_or_None)], 'steps': [(var, color_or_None)]}
                 (None = 변수 자리)
      slots    = {slot_name: {'kind': 'src'|'color', 'pos': i, 'values': [per-pair ...]}}
    파싱 실패/구조 불일치 시 (None, None)."""
    parsed = [parse_program(p) for p in programs]
    parsed = [p for p in parsed if p]
    if len(parsed) < 2:
        return None, None
    ndef = len(parsed[0]["defs"])
    nstep = len(parsed[0]["steps"])
    if any(len(p["defs"]) != ndef or len(p["steps"]) != nstep for p in parsed):
        return None, None            # 구조 다르면 이 골격으론 anti-unify 불가

    sk_defs, sk_steps, slots = [], [], {}
    for i in range(ndef):
        var = parsed[0]["defs"][i][0]
        vals = [p["defs"][i][1] for p in parsed]
        if len(set(vals)) == 1:                       # COMM → 상수
            sk_defs.append((var, vals[0]))
        else:                                         # DIFF → 변수 slot
            name = f"?src{i}"
            sk_defs.append((var, None))
            slots[name] = {"kind": "src", "pos": i, "var": var, "values": vals}
    for i in range(nstep):
        var = parsed[0]["steps"][i][0]
        vals = [p["steps"][i][1] for p in parsed]
        if len(set(vals)) == 1:
            sk_steps.append((var, vals[0]))
        else:
            name = f"?color{i}"
            sk_steps.append((var, None))
            slots[name] = {"kind": "color", "pos": i, "var": var, "values": vals}
    return {"defs": sk_defs, "steps": sk_steps}, slots


# ── resolve: 변수 slot → G0 유래 표현식 (generate → train 적용 → 대조 → 생존) ──────
# 하네스 §1-3/§4-1: 값을 손계산하지 않는다. 후보를 만들어 **train pair 로만** 검증하고
# (test 오라클 금지, §P5), 살아남은 것(version space)을 남긴다.
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


def resolve_slot(slot, train):
    """slot(kind='src'|'color', values=[per-pair]) 를 G0 유래 후보식으로 resolve.
    반환 (survivors=[(name, fn)], tried=[(name, ok)]). fn(grid)->value."""
    vals = slot["values"]
    if slot["kind"] == "src":                    # 픽셀 인덱스 slot
        cands = [("fg_index", _fg_index)]
    else:                                        # color slot
        cands = [("color_of_fg", _fg_color)]
    # 상수 후보(검색 정직성: DIFF 라 대개 기각됨 — 기각이 트레이스에 남는다 §1-5)
    cands += [(f"const {k}", (lambda g, k=k: k)) for k in sorted(set(vals))]
    tried, survivors = [], []
    for name, fn in cands:
        ok = len(train) == len(vals) and all(fn(train[i]["input"]) == vals[i]
                                             for i in range(len(vals)))
        tried.append((name, ok))
        if ok:
            survivors.append((name, fn))
    return survivors, tried


# ── 실행 + version space (resolved solution 을 test 입력에 실행) ──────────────────
def solution_candidates(sol, limit=3):
    """resolved version space 의 곱 → 후보 solution 목록 [(label, choice{name:fn})].
    slot 마다 생존식이 여럿이면(few-shot 애매성) 그 조합을 최대 limit 개까지 — 3-attempt."""
    import itertools
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
    """skeleton + slot별 선택 fn(choice[name]) → grid_in 에 실행 → 답 격자.
    var 의 픽셀 인덱스(상수 COMM 또는 resolved fn) 확정 후 coloring 단계 적용."""
    H, W = len(grid_in), len(grid_in[0])
    src_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "src"}
    col_at = {s["pos"]: n for n, s in slots.items() if s["kind"] == "color"}
    var_idx = {}
    for i, (var, idx) in enumerate(skeleton["defs"]):
        var_idx[var] = idx if idx is not None else choice[src_at[i]](grid_in)
    grid = [list(r) for r in grid_in]
    for i, (var, color) in enumerate(skeleton["steps"]):
        col = color if color is not None else choice[col_at[i]](grid_in)
        idx = var_idx.get(var)
        if idx is None:
            continue
        r, c = idx // W, idx % W
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = col
    return grid


def render_skeleton(skeleton, slots) -> str:
    """골격+변수 → 사람이 읽는 TASK.solution 문자열(대시보드·저장용)."""
    if not skeleton:
        return "{}"
    name_at = {("def", s["pos"]): n for n, s in slots.items() if s["kind"] == "src"}
    name_at.update({("step", s["pos"]): n for n, s in slots.items() if s["kind"] == "color"})
    lines = ["in_px = pixels_of(input_grid)"]
    for i, (var, idx) in enumerate(skeleton["defs"]):
        rhs = f"in_px[{idx}]" if idx is not None else f"in_px[{name_at[('def', i)]}]"
        lines.append(f"{var} = {rhs}")
    lines.append("")
    lines.append("tfg0 = input_grid")
    for i, (var, col) in enumerate(skeleton["steps"]):
        c = str(col) if col is not None else name_at[("step", i)]
        lines.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {var}.coord, {c})")
    lines.append(f"output_grid = tfg{len(skeleton['steps'])}")
    return "\n".join(lines)
