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


def cellset(cells_leaf):
    """blob target — 셀 집합(픽셀 인덱스)을 한 덩어리로. cells_leaf = {"const":[i,..]} | {"var":"?name"}."""
    return {"ref": "cellset", "cells": cells_leaf}


def _is_cellset_body(body):
    return bool(body) and all(s["args"]["target"].get("ref") == "cellset" for s in body)


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
    if _is_cellset_body(body):
        return _to_source_blob(body)
    # ── pixel/object 계열 (기존) ──
    src_lines, seen = [], set()
    for s in body:
        lvl = s["args"]["target"]["ref"]
        if lvl not in seen:
            seen.add(lvl); src_lines.append(_LEVEL[lvl][0])
    defs, steps = list(src_lines), ["tfg0 = input_grid"]
    for i, s in enumerate(body):
        tgt = s["args"]["target"]
        _, ref_name, prefix = _LEVEL[tgt["ref"]]
        defs.append(f"{prefix}{i} = {ref_name}[{_leaf_src(tgt['index'])}]")
        steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {prefix}{i}.coord, {_leaf_src(s['args']['color'])})")
    steps.append(f"output_grid = tfg{len(body)}")
    return "\n".join(defs + [""] + steps)


def _to_source_blob(body):
    """blob AST → 소스. 전부 const cells → compress def-형(정규식 round-trip); var 포함 → inline-형."""
    has_var = any("var" in s["args"]["target"]["cells"] for s in body)
    if not has_var:
        defs, steps = [], ["tfg0 = input_grid"]
        for j, s in enumerate(body):
            cells = list(s["args"]["target"]["cells"]["const"])
            defs.append(f"B{j} = {cells}")
            steps.append(f"tfg{j + 1} = apply_DSL(tfg{j}, coloring, B{j}, {_leaf_src(s['args']['color'])})")
        steps.append(f"output_grid = tfg{len(body)}")
        return "\n".join(defs + [""] + steps)
    lines = ["tfg0 = input_grid"]
    for j, s in enumerate(body):
        cl = s["args"]["target"]["cells"]
        cs = str(list(cl["const"])) if "const" in cl else cl["var"]
        lines.append(f"tfg{j + 1} = apply_DSL(tfg{j}, coloring, {cs}, {_leaf_src(s['args']['color'])})  # 객체 덩어리")
    lines.append(f"output_grid = tfg{len(body)}")
    return "\n".join(lines)


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
        col = _leaf_value(s["args"]["color"], grid_in, choice)
        if tgt.get("ref") == "cellset":                     # blob: 셀 집합 전체 채색 (execute_solution blob 분기)
            cl = tgt["cells"]
            cells = cl["const"] if "const" in cl else ((choice or {}).get(cl["var"], lambda g: None)(grid_in))
            if cells is None or col is None:
                continue
            for ix in cells:
                r, c = ix // W, ix % W
                if 0 <= r < H and 0 <= c < W:
                    grid[r][c] = col
            continue
        ix = _leaf_value(tgt["index"], grid_in, choice)      # pixel/object
        if ix is None or col is None:
            continue
        r, c = ix // W, ix % W
        if 0 <= r < H and 0 <= c < W:
            grid[r][c] = col
    return grid
