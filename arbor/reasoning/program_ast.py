# -*- coding: utf-8 -*-
"""ARBOR program AST — PAIR.program / TASK.solution 의 canonical 저장형.

균일 typed-arg nested-dict:
  program = {"input": {"grid": "G0"}, "body": [step...], "output": {"var": "grid"}, "slots"?: {...}}
  step    = {"call": op, "args": {name: leaf|node}}
  leaf    = {"const": v} | {"var": name} | {"expr": e} | {"ref": level, "index": leaf}
op ∈ frozen transformation atom (coloring, make_grid) 만. 그 외는 조합.

to_source(ast) 는 현행 flat Python 문자열과 바이트 동일을 낸다(이행 안전장치·복붙 실행용).
"""
from __future__ import annotations
import json


# ── 생성자 ──────────────────────────────────────────────
def const(v):                 return {"const": v}
def var(name):                return {"var": name}
def expr(e):                  return {"expr": e}
def ref(level, index_leaf):   return {"ref": level, "index": index_leaf}


def step(op, **args):
    return {"call": op, "args": dict(args)}


def program(body, input_grid="G0", output="grid", slots=None):
    p = {"input": {"grid": input_grid}, "body": list(body), "output": {"var": output}}
    if slots is not None:
        p["slots"] = slots
    return p


# ── leaf → 소스 조각 ────────────────────────────────────
def _leaf_src(leaf):
    """color/index leaf 를 소스 토큰으로. const=값, var/expr=이름/식 그대로."""
    if "const" in leaf:
        return str(leaf["const"])
    if "var" in leaf:
        return leaf["var"]
    if "expr" in leaf:
        return leaf["expr"]
    raise ValueError(f"bad leaf: {leaf}")


# ── to_source ───────────────────────────────────────────
_LEVEL = {"pixel": ("in_px = pixels_of(input_grid)", "in_px", "P"),
          "object": ("in_objs = objects_of(input_grid)", "in_objs", "O")}


def to_source(ast) -> str:
    """AST → 현행 flat Python 문자열 (없으면 sentinel '{}')."""
    if not ast or not ast.get("body"):
        return "{}"
    body = ast["body"]
    used = {}                                   # level → (src_line, ref_name, var_prefix)
    for s in body:
        tgt = s["args"]["target"]
        used.setdefault(tgt["ref"], _LEVEL[tgt["ref"]])
    # defs: 각 level 의 소스 선언 라인(등장 순), 그다음 스텝별 참조 정의
    defs = [v[0] for v in used.values()]
    steps = ["tfg0 = input_grid"]
    for i, s in enumerate(body):
        tgt = s["args"]["target"]
        _, ref_name, prefix = _LEVEL[tgt["ref"]]
        idx_src = _leaf_src(tgt["index"])
        col_src = _leaf_src(s["args"]["color"])
        defs.append(f"{prefix}{i} = {ref_name}[{idx_src}]")
        steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {prefix}{i}.coord, {col_src})")
    steps.append(f"output_grid = tfg{len(body)}")
    return "\n".join(defs + [""] + steps)


# ── execute ─────────────────────────────────────────────
def _leaf_value(leaf, grid_in, choice):
    """index/color leaf → 정수. const=값, var=choice[name](grid_in), expr 는 미지원(호출측이 var 로 변환)."""
    if "const" in leaf:
        return leaf["const"]
    if "var" in leaf:
        fn = (choice or {}).get(leaf["var"])
        return fn(grid_in) if fn else None
    raise ValueError(f"execute: unresolved leaf {leaf}")


def execute(ast, grid_in, choice=None):
    """AST 를 grid_in 에 실행 → 출력 grid. (숫자 처리 = antiunify.execute_solution 과 동일.)"""
    if not ast or not ast.get("body"):
        return [list(r) for r in grid_in]
    H, W = len(grid_in), len(grid_in[0])
    grid = [list(r) for r in grid_in]
    for s in ast["body"]:
        tgt = s["args"]["target"]
        ix = _leaf_value(tgt["index"], grid_in, choice)
        col = _leaf_value(s["args"]["color"], grid_in, choice)
        if ix is None or col is None:
            continue
        r, c = ix // W, ix % W
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = col
    return grid
