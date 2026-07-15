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


def _is_pixel_body(body):
    return bool(body) and all(s["args"]["target"].get("ref") == "pixel" for s in body)


# ── grid-property 생성자 (G1 = set_grid_size ∘ set_grid_color ∘ set_grid_contents) ──
def keep(prop):                 return {"keep": prop}
def delta(remove, add):         return {"delta": {"remove": list(remove), "add": list(add)}}
def set_grid_size(size_leaf):     return {"call": "set_grid_size", "args": {"size": size_leaf}}
def set_grid_color(color_leaf):   return {"call": "set_grid_color", "args": {"color": color_leaf}}
def set_grid_contents(c_leaf):    return {"call": "set_grid_contents", "args": {"contents": c_leaf}}


def grid_program(size_leaf, color_leaf, contents_leaf, input_grid="G0"):
    body = [set_grid_size(size_leaf), set_grid_color(color_leaf), set_grid_contents(contents_leaf)]
    return program(body, input_grid=input_grid)


_GRID_OPS = ("set_grid_size", "set_grid_color", "set_grid_contents")


def _is_grid_body(body):
    return bool(body) and all(s.get("call") in _GRID_OPS for s in body)


# ── grid_program_from_decide (_grid_decide → 3-property AST) ────
def _size_leaf(d):
    cands = d.get("cands") or []
    kinds = {k for k, _, ok in cands if ok}
    if "KEEP" in kinds:                    # 출력크기=입력크기
        return keep("size")
    for k, v, ok in cands:                 # MAP[H1=...] → expr
        if ok and k.startswith("MAP"):
            return expr(k[k.find("[") + 1:k.rfind("]")])
    h, w = d["value"]
    return const({"height": h, "width": w})


def _color_leaf(d):
    for k, v, ok in (d.get("cands") or []):
        if ok and k.startswith("KEEP"):
            return keep("color")
    # SET-MAP(-{rem}+{add}) 은 Phase 1 의 a/b(CONST) 가 안 타는 경로 → 구현 시 kind 문자열
    # "SET-MAP(-[..]+[..])" 를 파싱해 delta(remove, add) 로(또는 _grid_decide 가 remove/add 를
    # 구조로 노출하도록 값-파생 확장). 전역remap 태스크에서 골든으로 검증. Phase 1 필수 아님.
    return const(sorted(d["value"]))                       # 기본: 색집합 상수


def grid_program_from_decide(dec):
    if any(dec[p]["decision"] != "DECIDE" for p in ("size", "color", "contents")):
        return None
    cnote = dec["contents"].get("note")
    if cnote == "항등":
        c_leaf = keep("contents")
    elif cnote == "상수출력":
        c_leaf = const(dec["contents"]["value"])          # 입력-무관 고정 grid → 검증된 const 로 정직
    else:
        # 전역remap(등 입력-종속): dec["contents"]["value"] 는 test 입력에 remap 을 적용한 결과라, 이걸
        # const 로 구워 전 pair 에 물질화하면 train pair 는 자기 출력을 재현 못 함(비정직 §6/§1-5).
        # None 반환 → 호출측(hypothesize)이 하강해 기존 honest 경로(synthesize/_global_recolor_program)를 타게.
        return None
    return grid_program(_size_leaf(dec["size"]), _color_leaf(dec["color"]), c_leaf)


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


def _grid_leaf_src(leaf):
    """grid-property leaf → 소스 조각. keep/delta 는 전용 렌더, 그 외(const/var/expr) 는 _leaf_src 재사용."""
    if "keep" in leaf:
        return "keep"
    if "delta" in leaf:
        return f"-{leaf['delta']['remove']}+{leaf['delta']['add']}"
    return _leaf_src(leaf)


# ── to_source ───────────────────────────────────────────
_LEVEL = {"pixel": ("in_px = pixels_of(input_grid)", "in_px", "P"),
          "object": ("in_objs = objects_of(input_grid)", "in_objs", "O")}


def to_source(ast) -> str:
    """AST → 현행 flat Python 문자열 (없으면 sentinel '{}')."""
    if not ast or not ast.get("body"):
        return "{}"
    body = ast["body"]
    if _is_grid_body(body):
        return _to_source_grid(body)
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


def _to_source_grid(body):
    """grid body(set_grid_size/set_grid_color/set_grid_contents) → G0/G1 소스."""
    parts = {s["call"]: s["args"] for s in body}
    sz = _grid_leaf_src(parts["set_grid_size"]["size"])
    co = _grid_leaf_src(parts["set_grid_color"]["color"])
    ct = _grid_leaf_src(parts["set_grid_contents"]["contents"])
    return ("G0 = input_grid\n"
            f"G1 = set_grid_size({sz}) ∘ set_grid_color({co}) ∘ set_grid_contents({ct})\n"
            "output_grid = G1")


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
    if _is_grid_body(ast["body"]):
        return _execute_grid(ast["body"], grid_in, choice)
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


def _execute_grid(body, grid_in, choice):
    """set_grid_size/color/contents → make_grid+coloring lowering. contents 가 산출을 지배."""
    from procedural_memory.dsl.transformation import make_grid, coloring
    parts = {s["call"]: s["args"] for s in body}
    ct = parts["set_grid_contents"]["contents"]
    if "keep" in ct:                      # 항등 = G0
        return [list(r) for r in grid_in]
    if "const" in ct:                     # 상수/결정된 grid = 그대로 산출
        return [list(r) for r in ct["const"]]
    # 그 외(remap 등 leaf)는 Phase 1 범위 밖 → 항등 fallback (구현 확장 지점)
    return [list(r) for r in grid_in]


# ── render_header ───────────────────────────────────────
# level ref → 필요한 accessor DSL 이름
_LEVEL_ACCESSOR = {"pixel": "pixels_of", "object": "objects_of"}


def _sig(name):
    """SPECS 명세 → 한 줄 시그니처 (없으면 이름만)."""
    from procedural_memory.dsl.registry import SPECS
    s = SPECS.get(name)
    if not s:
        return f"# {name}(...)"
    return f"# {name}({', '.join(s['in'])}) -> {s['out']}"


def render_header(ast, grid_in) -> str:
    """AST 가 쓰는 op·accessor 시그니처 + 현 input_grid. 저장 안 함(표시/복붙용)."""
    import json as _json
    ops, accs = [], []
    for s in (ast.get("body") or []):
        if s["call"] not in ops:
            ops.append(s["call"])
        lvl = s["args"]["target"]["ref"]
        acc = _LEVEL_ACCESSOR.get(lvl)
        if acc and acc not in accs:
            accs.append(acc)
    lines = ["# --- DSL (used) ---"]
    lines += [_sig(n) for n in ops + accs]
    lines += ["# --- input (this pair) ---", f"input_grid = {_json.dumps(grid_in)}"]
    return "\n".join(lines)


# ── as_source (읽기 지점 정규화 shim) ─────────────────────
def as_source(wm_value):
    """WM 저장값(legacy flat 문자열 | AST-json | None | '{}') → flat 문자열('{}'=미합성)."""
    if wm_value in (None, "{}", ""):
        return "{}"
    if isinstance(wm_value, str) and wm_value.lstrip().startswith("{"):
        try:
            obj = json.loads(wm_value)
        except (ValueError, TypeError):
            return wm_value
        if isinstance(obj, dict) and ("body" in obj or "input" in obj):
            return to_source(obj)
        return wm_value          # '{}' 등 program 아닌 dict
    return wm_value


# ── ops_of_ast / antiunify_ast ───────────────────────────
def ops_of_ast(ast):
    """concrete AST → [(target_value, color)]. pixel=idx, cellset=frozenset(cells). slot(var)=None."""
    ops = []
    for s in (ast.get("body") or []):
        tgt = s["args"]["target"]
        col_leaf = s["args"]["color"]
        col = col_leaf.get("const") if "const" in col_leaf else None
        if tgt.get("ref") == "cellset":
            cl = tgt["cells"]
            cells = frozenset(cl["const"]) if "const" in cl else None
            ops.append((cells, col))
        else:
            idx_leaf = tgt["index"]
            idx = idx_leaf.get("const") if "const" in idx_leaf else None
            ops.append((idx, col))
    return ops


def antiunify_ast(asts):
    """정렬된 per-pair AST 들 → (skeleton_ast, slots). 계열 판별: 전부 grid body → grid 경로,
    전부 cellset body → blob 경로, 아니면 pixel 경로. 위치별 COMM=상수, DIFF=var 승격.
    op 수 다르면 (None, None)."""
    valid = [a for a in asts if a and a.get("body")]
    if len(valid) < 2:
        return None, None
    if all(_is_grid_body(a["body"]) for a in valid):
        return _antiunify_ast_grid(valid)
    if all(_is_cellset_body(a["body"]) for a in valid):
        return _antiunify_ast_blob(valid)
    return _antiunify_ast_pixel(valid)


def _antiunify_ast_grid(asts):
    """grid(3-property) AST 들 → (skeleton, slots). pixel/blob 처럼 op 위치가 아니라
    property key(size/color/contents) 별로 비교: leaf 동일=COMM(그대로 유지), 다르면
    DIFF → {"var":"?<prop>"} + slot."""
    import json as _json
    props = [("set_grid_size", "size"), ("set_grid_color", "color"), ("set_grid_contents", "contents")]
    body, slots = [], {}
    partsN = [{s["call"]: s["args"] for s in a["body"]} for a in asts]
    for call, key in props:
        leaves = [pn[call][key] for pn in partsN]
        same = all(_json.dumps(x, sort_keys=True) == _json.dumps(leaves[0], sort_keys=True) for x in leaves)
        if same:
            leaf = leaves[0]
        else:
            leaf = {"var": f"?{key}"}
            slots[f"?{key}"] = {"kind": key, "pos": key, "values": leaves}
        body.append({"call": call, "args": {key: leaf}})
    return program(body, slots=slots), slots


def _antiunify_ast_pixel(asts):
    from arbor.reasoning.antiunify import _align
    asts = [a for a in asts if _is_pixel_body(a.get("body") or [])]   # ← object body 제외(레거시 parse None 대응)
    progs = [ops_of_ast(a) for a in asts]
    progs = [p for p in progs if p and all(o[0] is not None for o in p)]
    if len(progs) < 2:
        return None, None
    n = len(progs[0])
    if any(len(p) != n for p in progs):
        return None, None
    ref_ops = progs[0]
    aligned = [ref_ops] + [_align(ref_ops, p) for p in progs[1:]]
    body, slots = [], {}
    for i in range(n):
        idxs = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_idx = idxs[0] if len(set(idxs)) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        idx_leaf = const(sk_idx) if sk_idx is not None else var(f"?src{i}")
        col_leaf = const(sk_col) if sk_col is not None else var(f"?color{i}")
        if sk_idx is None:
            slots[f"?src{i}"] = {"kind": "src", "pos": i, "values": idxs}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        body.append(step("coloring", target=ref("pixel", idx_leaf), color=col_leaf))
    return program(body, slots=slots), slots


def _antiunify_ast_blob(asts):
    """blob AST 들 → (skeleton, slots). _align_blobs(색 COMM 정렬) 재사용. cellset DIFF → cellset slot.
    (antiunify.py::_antiunify_blobs 를 AST 로 mirror; 셀집합 비교는 tuple(sorted) 정규화.)"""
    from arbor.reasoning.antiunify import _align_blobs
    progs = [ops_of_ast(a) for a in asts]
    progs = [p for p in progs if p and all(o[0] is not None for o in p)]   # concrete cells 만
    if len(progs) < 2:
        return None, None
    n = len(progs[0])
    if any(len(p) != n for p in progs):
        return None, None
    ref_ops = progs[0]
    aligned = [ref_ops] + [_align_blobs(ref_ops, p) for p in progs[1:]]
    body, slots = [], {}
    for i in range(n):
        cellsets = [a[i][0] for a in aligned]
        cols = [a[i][1] for a in aligned]
        sk_cells = cellsets[0] if len({tuple(sorted(c)) for c in cellsets}) == 1 else None
        sk_col = cols[0] if len(set(cols)) == 1 else None
        cells_leaf = const(sorted(sk_cells)) if sk_cells is not None else var(f"?cells{i}")
        col_leaf = const(sk_col) if sk_col is not None else var(f"?color{i}")
        if sk_cells is None:
            slots[f"?cells{i}"] = {"kind": "cellset", "pos": i, "values": [sorted(c) for c in cellsets]}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        body.append(step("coloring", target=cellset(cells_leaf), color=col_leaf))
    return program(body, slots=slots), slots
