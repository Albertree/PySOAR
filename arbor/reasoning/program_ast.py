# -*- coding: utf-8 -*-
"""ARBOR program AST — PAIR.program / TASK.solution 의 canonical 저장형.

균일 typed-arg nested-dict:
  program = {"input": {"grid": "G0"}, "body": [step...], "output": {"var": "grid"}, "slots"?: {...}}
  step    = {"call": op, "args": {name: leaf|node}}
  leaf    = {"const": v} | {"var": name} | {"expr": e} | {"ref": level, "index": leaf}
op ∈ frozen transformation atom (coloring) 만. 그 외는 조합.

to_source(ast) 는 현행 flat Python 문자열과 바이트 동일을 낸다(이행 안전장치·복붙 실행용).
"""
from __future__ import annotations
import json


# ── 생성자 ──────────────────────────────────────────────
def const(v):                 return {"const": v}
def var(name):                return {"var": name}
def expr(e):                  return {"expr": e}
def ref(level, index_leaf):   return {"ref": level, "index": index_leaf}
def pending(prop):            return {"pending": prop}


# ── Grammar A: 조건-선택 표현 (cellset 대체) ──────────────
def eq(accessor, value):
    """직렬화되는 술어 노드: accessor(property DSL 함수명) 의 값이 value 와 같은가."""
    return {"eq": {"accessor": accessor, "value": value}}


def coord_in(accessor, values):
    """membership 술어: accessor(node) 의 값이 values 집합에 속함 (eq 의 집합판; coord 리스트 등)."""
    return {"in": {"accessor": accessor, "values": values}}


def select(grid, level, pred):
    """grid(노드참조 문자열 또는 'input' 마커) 아래 level 요소 중 pred 맞는 것.
    실행 시 raw grid 로부터 ARCKG 노드를 만들어 pixels_of/objects_of + pred 로 해소."""
    return {"select": {"grid": grid, "level": level, "pred": pred}}


def coordinate_of(x):
    """선택결과 → 좌표(들). coloring target 으로 쓰는 래핑."""
    return {"coordinate_of": x}


def cellset(cells_leaf):
    """blob target — 셀 집합(픽셀 인덱스)을 한 덩어리로. cells_leaf = {"const":[i,..]} | {"var":"?name"}."""
    return {"ref": "cellset", "cells": cells_leaf}


def contents_program(body):
    """grid contents leaf — nested coloring 합성(하강 산출). body = pixel/object/cellset coloring step 들."""
    return {"program": {"body": list(body)}}


def _is_cellset_body(body):
    return bool(body) and all(s["args"]["target"].get("ref") == "cellset" for s in body)


def _is_select_body(body):
    return bool(body) and all("coordinate_of" in s["args"]["target"] for s in body)


def _is_pixel_body(body):
    return bool(body) and all(s["args"]["target"].get("ref") in ("pixel", "coord") for s in body)


# ── grid-property 생성자 (G1 = set_grid_size ∘ set_grid_color ∘ set_grid_contents) ──
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
        return expr("size(input_grid)")
    for k, v, ok in cands:                 # MAP[H1=...] → expr
        if ok and k.startswith("MAP"):
            return expr(k[k.find("[") + 1:k.rfind("]")])
    h, w = d["value"]
    return const({"height": h, "width": w})


def _color_leaf(d):
    for k, v, ok in (d.get("cands") or []):
        if ok and k.startswith("KEEP"):
            return expr("color(input_grid)")
    # SET-MAP(-{rem}+{add}) 은 Phase 1 의 a/b(CONST) 가 안 타는 경로 → 구현 시 kind 문자열
    # "SET-MAP(-[..]+[..])" 를 파싱해 delta(remove, add) 로(또는 _grid_decide 가 remove/add 를
    # 구조로 노출하도록 값-파생 확장). 전역remap 태스크에서 골든으로 검증. Phase 1 필수 아님.
    return const(sorted(d["value"]))                       # 기본: 색집합 상수


def _slot_leaf(dec, prop, leaf_fn):
    """결정된 슬롯(size/color) → 실제 leaf. 미결(DESCEND/AMBIGUOUS) → pending placeholder(하강해서
    채울 자리 — 버리지 않고 골격에 표시만 해둔다)."""
    d = dec[prop]
    if d["decision"] != "DECIDE":
        return pending(prop)
    return leaf_fn(d)


def grid_program_from_decide(dec):
    """size/color/contents 부분결정도 **skeleton** 으로 낸다(폐기 None 없음): 결정된 슬롯은 leaf,
    미결 슬롯은 `pending(prop)` placeholder. 셋 다 결정되면 현행과 byte-identical 한 full program
    (`is_full_grid_program` 로 판별) — a/b 는 이 경로. c–h 는 size/color leaf + contents=pending."""
    size_leaf = _slot_leaf(dec, "size", _size_leaf)
    color_leaf = _slot_leaf(dec, "color", _color_leaf)

    cdec = dec["contents"]
    if cdec["decision"] != "DECIDE":
        c_leaf = pending("contents")
    else:
        cnote = cdec.get("note")
        if cnote == "항등":
            c_leaf = expr("contents(input_grid)")
        elif cnote == "상수출력":
            c_leaf = const(cdec["value"])                  # 입력-무관 고정 grid → 검증된 const 로 정직
        else:
            # 입력-종속 contents(재채색 등): const 로 구워 전 pair 에 물질화하면 train pair 는 자기 출력을
            # 재현 못 함(비정직 §6/§1-5). pending 처리 → 호출측(hypothesize)이 하강해 honest 객체선택 경로
            # (synthesize → pixel → object → anti-unify)를 타게 한다.
            c_leaf = pending("contents")
    return grid_program(size_leaf, color_leaf, c_leaf)


def grid_inner_op_counts(ast):
    """grid>pixel/blob 이면 set_grid_contents 의 nested program body 길이 [n], 아니면 None."""
    body = (ast or {}).get("body") or []
    if not _is_grid_body(body):
        return None
    for s in body:
        if s["call"] == "set_grid_contents":
            leaf = s["args"]["contents"]
            if "program" in leaf:
                return [len(leaf["program"]["body"])]
    return None


def is_full_grid_program(gp):
    """gp 의 body 어느 leaf 에도 `pending` 이 없으면 True(전 슬롯 결정 = 물질화 가능).
    partial(하강 필요한 슬롯 있음) 이면 False. gp 가 falsy 면 False."""
    if not gp:
        return False
    for s in gp.get("body") or []:
        for leaf in (s.get("args") or {}).values():
            if isinstance(leaf, dict) and "pending" in leaf:
                return False
    return True


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
    if "pending" in leaf:                       # 하강으로 아직 못 채운 슬롯(미결정) — 크래시 대신 정직 표기
        return f"<{leaf['pending']}?>"
    raise ValueError(f"bad leaf: {leaf}")


def _sel_src(target):
    """coordinate_of(select(...)) target → 소스 조각. select-target 이 아니면 None."""
    if "coordinate_of" not in target:
        return None
    inner = target["coordinate_of"]
    sel = inner.get("select")
    if sel is None:
        return None
    pred = sel["pred"]
    if "in" in pred:
        p = pred["in"]
        return f"coordinate_of(select({sel['grid']}, {sel['level']}, {p['accessor']}∈{p['values']}))"
    p = pred["eq"]
    return f"coordinate_of(select({sel['grid']}, {sel['level']}, {p['accessor']}=={p['value']}))"


def _contents_program_src(body):
    """contents leaf `program`(nested coloring 합성 — T4 하강 산출) → 소스 조각. 기존 pixel/object
    coloring step 표기를 재사용(파싱 계약은 안 늘림 — 표시 전용, `parse_program` 은 이 형태를 못
    읽고 None 을 내면 그걸로 충분: compressible()/legacy 경로는 grid AST 를 대상으로 하지 않는다)."""
    parts = []
    for s in body:
        tgt = s["args"]["target"]
        col = _leaf_src(s["args"]["color"])
        sel = _sel_src(tgt)
        if sel is not None:
            parts.append(f"coloring({sel}, color={col})")
            continue
        if tgt.get("ref") == "cellset":
            cl = tgt["cells"]
            cells = str(cl["const"]) if "const" in cl else _leaf_src(cl)
            parts.append(f"coloring(cellset={cells}, color={col})")
        elif tgt.get("ref") == "coord":
            parts.append(f"coloring({tuple(tgt['index']['const'])}, color={col})")
        else:
            parts.append(f"coloring({tgt.get('ref')}[{_leaf_src(tgt['index'])}], color={col})")
    return " ∘ ".join(parts) if parts else "identity"


def _grid_leaf_src(leaf):
    """grid-property leaf → 소스 조각. delta 는 전용 렌더, program(하강 coloring 합성) 은
    `_contents_program_src`, 그 외(const/var/expr) 는 _leaf_src 재사용."""
    if "delta" in leaf:
        return f"-{leaf['delta']['remove']}+{leaf['delta']['add']}"
    if "program" in leaf:
        return _contents_program_src(leaf["program"]["body"])
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
    # ── pixel/object/coord 계열 ──
    src_lines, seen = [], set()
    for s in body:
        lvl = s["args"]["target"].get("ref")          # select-target(coordinate_of) 엔 "ref" 없음 → None
        if lvl in _LEVEL and lvl not in seen:                 # coord 는 헤더(in_px=..) 불필요
            seen.add(lvl); src_lines.append(_LEVEL[lvl][0])
    defs, steps = list(src_lines), ["tfg0 = input_grid"]
    for i, s in enumerate(body):
        tgt = s["args"]["target"]; col = _leaf_src(s["args"]["color"])
        sel = _sel_src(tgt)
        if sel is not None:
            steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {sel}, {col})")
            continue
        if tgt["ref"] == "coord":                             # 리터럴 좌표 직접
            pos = tuple(tgt["index"]["const"]) if "const" in tgt["index"] else _leaf_src(tgt["index"])
            steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {pos}, {col})")
        else:
            _, ref_name, prefix = _LEVEL[tgt["ref"]]
            defs.append(f"{prefix}{i} = {ref_name}[{_leaf_src(tgt['index'])}]")
            steps.append(f"tfg{i + 1} = apply_DSL(tfg{i}, coloring, {prefix}{i}.coord, {col})")
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


def _norm_coord(v):
    """property 좌표값 정규화: {"row_index":r,"col_index":c} → (r,c); list/tuple → tuple; 그 외 그대로."""
    if isinstance(v, dict) and "row_index" in v and "col_index" in v:
        return (v["row_index"], v["col_index"])
    if isinstance(v, (list, tuple)):
        return tuple(v)
    return v


def _accessor_fn(name):
    """accessor 이름 → callable(node)->value. property DSL 함수명이면 그 함수, 아니면
    node.to_json()[name](= property KEY). (사용자 2026-07-24: accessor 를 **검색가능한 property key**
    이름으로 통일 — pixel 좌표는 함수명 pixel_coordinate 가 아니라 key 'coordinate'.)"""
    from procedural_memory.dsl import property as _prop   # vendored property DSL
    fn = getattr(_prop, name, None)
    if fn is not None:
        return fn
    return lambda node: node.to_json().get(name)


def _compile_pred(pred):
    """eq·in 술어 노드 → callable(node)->bool. accessor = property key(또는 DSL 함수명).
    eq = 단일값 일치, in = values 집합 소속(eq 의 집합판; 다중 셀을 한 select 로 고르기 위함)."""
    if "eq" in pred:
        e = pred["eq"]
        accessor = _accessor_fn(e["accessor"])
        want = _norm_coord(e["value"])

        def ok(node):
            return _norm_coord(accessor(node)) == want
        return ok
    if "in" in pred:
        e = pred["in"]
        accessor = _accessor_fn(e["accessor"])
        wants = {_norm_coord(v) for v in e["values"]}

        def ok_in(node):
            return _norm_coord(accessor(node)) in wants
        return ok_in
    raise ValueError(f"bad pred {pred}")


def _select_values_var(target):
    """coordinate_of(select(...coord_in(var))) 의 var 이름 반환. values 가 var 슬롯이 아니면 None.
    (const 좌표목록은 _resolve_select_coords 로, var 는 choice[var] 로 해소 — cellset-var 와 대칭.)"""
    if "coordinate_of" not in target:
        return None
    sel = target["coordinate_of"].get("select")
    if not sel:
        return None
    vals = ((sel.get("pred") or {}).get("in") or {}).get("values")
    if isinstance(vals, dict) and "var" in vals:
        return vals["var"]
    return None


def _resolve_select_coords(target, grid_in):
    """coordinate_of(select("input", level, pred)) → [(r,c)...] (정렬). select-target 아니면 None."""
    if "coordinate_of" not in target:
        return None
    sel = target["coordinate_of"].get("select")
    if sel is None:
        return None
    from arbor.perception.arckg.grid import Grid
    from procedural_memory.dsl.util import pixels_of, objects_of
    gnode = Grid("_exec", grid_in)
    pred = _compile_pred(sel["pred"])
    if sel["level"] == "pixel":
        chosen = [p for p in pixels_of(gnode) if pred(p)]
        coords = [tuple(p.coord) for p in chosen]
    else:                                                    # object (P2 에서 본격 사용)
        from procedural_memory.dsl.property import coordinate_of as _coord_of
        chosen = [o for o in objects_of(gnode) if pred(o)]
        coords = [tuple(rc) for o in chosen for rc in _coord_of(o)]
    return sorted(coords)


# ── execute ─────────────────────────────────────────────
def _leaf_value(leaf, grid_in, choice):
    """index/color leaf → 정수. const=값, var=choice[name](grid_in), expr 는 미지원(호출측이 var 로 변환)."""
    if "const" in leaf:
        return leaf["const"]
    if "var" in leaf:
        fn = (choice or {}).get(leaf["var"])
        return fn(grid_in) if fn else None
    raise ValueError(f"execute: unresolved leaf {leaf}")


def _execute_pixel_body(body, grid_in, choice):
    """pixel/object/cellset coloring body → 출력 grid. (기존 execute 의 for 문 그대로 이동.)"""
    H, W = len(grid_in), len(grid_in[0])
    grid = [list(r) for r in grid_in]
    for s in body:
        tgt = s["args"]["target"]
        col = _leaf_value(s["args"]["color"], grid_in, choice)
        svar = _select_values_var(tgt)                       # select 의 coord_in.values 가 var 슬롯이면
        if svar is not None:                                 # choice[var] 로 셀을 해소(cellset-var 와 대칭)
            fn = (choice or {}).get(svar)
            cells = fn(grid_in) if fn else None              # resolve 산출 = 픽셀 인덱스(cellset-var 동치)
            if cells is not None and col is not None:
                for (r, c) in sorted((ix // W, ix % W) for ix in cells):
                    if 0 <= r < H and 0 <= c < W:
                        grid[r][c] = col
            continue
        coords = _resolve_select_coords(tgt, grid_in)
        if coords is not None:
            if col is not None:
                for (r, c) in coords:
                    if 0 <= r < H and 0 <= c < W:
                        grid[r][c] = col
            continue
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
        if tgt.get("ref") == "coord":                       # 리터럴 좌표 (r,c) 직접
            pos = _leaf_value(tgt["index"], grid_in, choice)
            if pos is None or col is None:
                continue
            r, c = pos
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


def execute(ast, grid_in, choice=None):
    """AST 를 grid_in 에 실행 → 출력 grid. (숫자 처리 = antiunify.execute_solution 과 동일.)"""
    if not ast or not ast.get("body"):
        return [list(r) for r in grid_in]
    if _is_grid_body(ast["body"]):
        return _execute_grid(ast["body"], grid_in, choice)
    return _execute_pixel_body(ast["body"], grid_in, choice)


def _execute_grid(body, grid_in, choice):
    """set_grid_size/color/contents → make_grid+coloring lowering. contents 가 산출을 지배."""
    parts = {s["call"]: s["args"] for s in body}
    ct = parts["set_grid_contents"]["contents"]
    if "const" in ct:                     # 상수/결정된 grid = 그대로 산출
        return [list(r) for r in ct["const"]]
    if "program" in ct:                                   # nested coloring 합성 = 하강 산출
        return _execute_pixel_body(ct["program"]["body"], grid_in, choice)
    # 그 외(expr(항등 등)/remap 등 leaf)는 Phase 1 범위 밖 → 항등 fallback (구현 확장 지점)
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
        lvl = s["args"]["target"].get("ref")
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
        if "coordinate_of" in tgt:                       # select-target → coord_in.values 를 cellset shape 로
            sel = tgt["coordinate_of"].get("select") or {}
            vals = ((sel.get("pred") or {}).get("in") or {}).get("values")
            cells = frozenset(tuple(c) for c in vals) if isinstance(vals, list) else None
            ops.append((cells, col))
        elif tgt.get("ref") == "cellset":
            cl = tgt["cells"]
            cells = frozenset(cl["const"]) if "const" in cl else None
            ops.append((cells, col))
        else:
            idx_leaf = tgt["index"]
            idx = idx_leaf.get("const") if "const" in idx_leaf else None
            if isinstance(idx, list):                        # coord [r,c] → 해시가능 튜플 키
                idx = tuple(idx)
            ops.append((idx, col))
    return ops


def antiunify_ast(asts, force_slots=False):
    """정렬된 per-pair AST 들 → (skeleton_ast, slots). 계열 판별: 전부 grid body → grid 경로,
    전부 cellset body → blob 경로, 아니면 pixel 경로. 위치별 COMM=상수, DIFF=var 승격.
    op 수 다르면 (None, None).
    force_slots: 이동(move) 프로그램에선 cellset(이동객체 위치)이 관계적이므로 train 우연으로 일치해도
      const 로 굽지 않고 slot 화 → resolve 가 move@anchor 로 일반화(§move am 좌표절대). (color 는 현재
      강제 안 함 — 배경색까지 slot화하면 version space 부풀어 회귀; 도착색만 강제하는 수술적 수정 후속.)"""
    valid = [a for a in asts if a and a.get("body")]
    if len(valid) < 2:
        return None, None
    if all(_is_grid_body(a["body"]) for a in valid):
        return _antiunify_ast_grid(valid, force_slots)
    if all(_is_cellset_body(a["body"]) for a in valid):
        return _antiunify_ast_blob(valid, force_slots)
    if all(_is_select_body(a["body"]) for a in valid):
        return _antiunify_ast_select(valid, force_slots)
    return _antiunify_ast_pixel(valid)


def _reprefix_inner_vars(leaf, prefix):
    """leaf(= {"program": {"body": [...]}}) 안의 모든 {"var":"?name"} 을 {"var":"<prefix>name[1:]"} 로
    재바인딩. slots 승격(키 = prefix + name[1:])과 일관되도록 skeleton 쪽 var 이름도 맞춰준다."""
    def _fix_var(v):
        if isinstance(v, dict) and "var" in v and isinstance(v["var"], str) and v["var"].startswith("?"):
            return {"var": f"{prefix}{v['var'][1:]}"}
        return v

    new_body = []
    for s in leaf["program"]["body"]:
        tgt = s["args"]["target"]
        new_tgt = dict(tgt)
        if "index" in new_tgt:
            new_tgt["index"] = _fix_var(new_tgt["index"])
        if "cells" in new_tgt:                  # unreachable: _antiunify_ast_pixel emits only pixel targets
            new_tgt["cells"] = _fix_var(new_tgt["cells"])
        if "coordinate_of" in new_tgt:          # select-target: var 은 coord_in.values 밑에 있음
            co = new_tgt["coordinate_of"]
            sel = (co or {}).get("select")
            if sel and "in" in (sel.get("pred") or {}):
                pin = dict(sel["pred"]["in"])
                pin["values"] = _fix_var(pin["values"])
                new_tgt["coordinate_of"] = dict(co, select=dict(sel, pred=dict(sel["pred"], **{"in": pin})))
        new_args = dict(s["args"], target=new_tgt, color=_fix_var(s["args"]["color"]))
        new_body.append({"call": s["call"], "args": new_args})
    return {"program": {"body": new_body}}


def _antiunify_ast_grid(asts, force_slots=False):
    """grid(3-property) AST 들 → (skeleton, slots). pixel/blob 처럼 op 위치가 아니라
    property key(size/color/contents) 별로 비교: leaf 동일=COMM(그대로 유지), 다르면
    DIFF → {"var":"?<prop>"} + slot. 단 contents leaf 가 전 pair 에서 program(nested coloring)
    이면 leaf 를 통째로 var 슬롯화하지 않고, inner body 를 _antiunify_ast_pixel 로 재귀 anti-unify
    한 뒤 inner slot(?srcN/?colorN) 을 top-level 로 승격(prefix ?c.)한다."""
    import json as _json
    props = [("set_grid_size", "size"), ("set_grid_color", "color"), ("set_grid_contents", "contents")]
    body, slots = [], {}
    partsN = [{s["call"]: s["args"] for s in a["body"]} for a in asts]
    for call, key in props:
        leaves = [pn[call][key] for pn in partsN]
        if call == "set_grid_contents" and all("program" in leaf for leaf in leaves):
            inner_asts = [program(leaf["program"]["body"]) for leaf in leaves]
            if all(_is_cellset_body(ia["body"]) for ia in inner_asts):
                sk_inner, inner_slots = _antiunify_ast_blob(inner_asts, force_slots)
            elif all(_is_select_body(ia["body"]) for ia in inner_asts):
                sk_inner, inner_slots = _antiunify_ast_select(inner_asts, force_slots)
            else:
                sk_inner, inner_slots = _antiunify_ast_pixel(inner_asts)
            if sk_inner is None:                                # structural mismatch (op-count 불일치 등)
                return None, None
            leaf = {"program": {"body": (sk_inner or {}).get("body", [])}}
            for nm, meta in (inner_slots or {}).items():        # top-level 로 승격(prefix)
                slots[f"?c.{nm[1:]}"] = meta
            leaf = _reprefix_inner_vars(leaf, "?c.")             # inner body 의 var 이름도 재바인딩(일관)
            body.append({"call": call, "args": {key: leaf}})
            continue
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
        if isinstance(sk_idx, tuple):                        # coord 입력 → coord 스켈레톤(리터럴 유지)
            body.append(step("coloring", target=ref("coord", const(list(sk_idx))), color=col_leaf))
        else:
            body.append(step("coloring", target=ref("pixel", idx_leaf), color=col_leaf))
    return program(body, slots=slots), slots


def _cellset_target(sorted_cells, var_name):
    """blob 스켈레톤 target: COMM(sorted_cells=list) → cellset(const), DIFF(None) → cellset(var)."""
    return cellset(const(sorted_cells) if sorted_cells is not None else var(var_name))


def _select_target(sorted_cells, var_name):
    """select 스켈레톤 target: COMM → coord_in const 좌표목록, DIFF → coord_in var. cellset 과 동치(좌표)."""
    cells_leaf = const([list(c) for c in sorted_cells]) if sorted_cells is not None else var(var_name)
    return coordinate_of(select("input", "pixel", coord_in("coordinate", cells_leaf)))


def _antiunify_ast_group(asts, force_slots, make_target):
    """cellset/select 공통 코어: ops_of_ast 가 같은 (cells, color) shape 를 내므로 정렬·COMM/DIFF·slot 로직을
    공유하고, 위치별 스켈레톤 target 만 `make_target(sorted_cells|None, var_name)` 로 분기 emit(DRY).
    반환 = (body, slots) 원자 — program 래핑(슬롯 임베드 여부)은 호출측(blob/select)이 결정.
    _align_blobs(색 COMM 최대화 순열)로 정렬. 셀집합 비교는 tuple(sorted) 정규화.
    force_slots=True(이동) → 셀집합 일치해도 const 로 굽지 않고 항상 slot 화(color 는 제외).
    구조 불일치(concrete cells 부족·op수 상이) → (None, None)."""
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
        same_cells = len({tuple(sorted(c)) for c in cellsets}) == 1
        sk_cells = cellsets[0] if (same_cells and not force_slots) else None
        sk_col = cols[0] if len(set(cols)) == 1 else None   # (색 강제 slot화 실험 보류 — au 만 이득, 부작용 검증중)
        col_leaf = const(sk_col) if sk_col is not None else var(f"?color{i}")
        target = make_target(sorted(sk_cells) if sk_cells is not None else None, f"?cells{i}")
        if sk_cells is None:
            slots[f"?cells{i}"] = {"kind": "cellset", "pos": i, "values": [sorted(c) for c in cellsets]}
        if sk_col is None:
            slots[f"?color{i}"] = {"kind": "color", "pos": i, "values": cols}
        body.append(step("coloring", target=target, color=col_leaf))
    return body, slots


def _antiunify_ast_blob(asts, force_slots=False):
    """blob(cellset) AST 들 → (skeleton, slots). 공통 코어에 cellset target emit 만 주입.
    (기존 동작 유지 — 슬롯을 skeleton 에 임베드.)"""
    body, slots = _antiunify_ast_group(asts, force_slots, _cellset_target)
    if body is None:
        return None, None
    return program(body, slots=slots), slots


def _antiunify_ast_select(asts, force_slots=False):
    """select(coordinate_of(select(...coord_in))) AST 들 → (skeleton, slots). cellset 과 동치 로직,
    스켈레톤만 select-target 으로 emit(COMM=const coord_in, DIFF=var coord_in). slot kind 는 "cellset"
    유지(다음 task resolve 가 그대로 소비) · values 는 좌표(r,c) 목록. skeleton 자체엔 슬롯을 임베드하지
    않는다 — canonical slots 는 tuple 2nd 요소(generalize 가 sk["slots"] 를 이걸로 덮어씀)이고, 그래야
    skeleton body 가 cellset 표기 없이 순수 select 표현으로 남는다(cellset 동치의 대체 표현)."""
    body, slots = _antiunify_ast_group(asts, force_slots, _select_target)
    if body is None:
        return None, None
    return program(body), slots
