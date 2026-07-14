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
