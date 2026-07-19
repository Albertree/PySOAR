# -*- coding: utf-8 -*-
"""TASK.solution 표현식 렌더 — 솔버 선택자/resolved 를 함수·symbol 조합 표현식으로 재표기.
설계: docs/superpowers/specs/2026-07-20-solution-expression-viz-design.md. 시각화-먼저(솔버 불변).
금지: count·output_grid symbol (P5, input_grid 만)."""
from __future__ import annotations
import re


def selector_to_condition(sel):
    """솔버 선택자 이름 → (select 조건식, shape_ref|None). 채택된 선택자 충실 렌더.
    bounded → color(o) != 0 (표현계층 색0≠배경 완화, 설계 §3-2)."""
    if not sel:
        return "true", None
    if sel.startswith("color="):
        return f"color(o) == {sel[len('color='):]}", None
    if sel.startswith("size="):
        return f"area(o) == {sel[len('size='):]}", None
    if sel == "bounded":
        return "color(o) != 0", None
    if sel.startswith("shape#"):
        ref = f"shape{sel[len('shape#'):]}"
        return f"shape(o) == {ref}", ref
    return sel, None                       # 정직 fallback (row=/col= 등 move 미사용)


def _parse_axis(tok):
    """이동 축 토큰 → (kind, target, anchor_comp_kind). kind: rel|abs|edge|corner|br|raw.
    anchor_comp_kind: 'tl'(top_left)|'br'(bottom_right)|'0'(없음=상대). target: int|'corner'|str."""
    m = re.match(r"^[rc]0([+-]\d+)$", tok)
    if m:
        return ("rel", int(m.group(1)), "0")
    if tok.startswith("BR="):
        return ("br", int(tok[len("BR="):]), "br")
    if tok.startswith("="):
        return ("abs", int(tok[len("="):]), "tl")
    if tok == "0":
        return ("edge", 0, "tl")
    if tok in ("H-h", "W-w"):
        return ("corner", "corner", "br")
    return ("raw", tok, "0")


def move_to_vector(row_tok, col_tok, objvar):
    """resolved move[ROW,COL] → 벡터-산술 표현식(설계 §3-4). 같은-모델은 깔끔형, 혼합은 성분별."""
    r = _parse_axis(row_tok)
    c = _parse_axis(col_tok)
    coord = f"coordinate({objvar})"
    # 제자리(둘 다 rel Δ0)
    if r[0] == "rel" and c[0] == "rel":
        if r[1] == 0 and c[1] == 0:
            return coord
        return f"{coord} + ({r[1]}, {c[1]})"
    # 둘 다 격자코너: GRID 는 size/color/contents 만 가짐(코너 property 없음). 격자 우하코너 = (H-1, W-1)
    # = (height(input_grid)-1, width(input_grid)-1). bottom_right(input_grid) 는 무효(사용자 2026-07-20).
    if r[0] == "corner" and c[0] == "corner":
        return f"{coord} - bottom_right({objvar}) + (height(input_grid) - 1, width(input_grid) - 1)"
    # 앵커 성분(각 축)과 target 성분
    def _anchor(comp, axis):                       # axis: 'row'|'col'
        if comp == "tl":
            return f"top_left({objvar}).{axis}"
        if comp == "br":
            return f"bottom_right({objvar}).{axis}"
        return "0"                                 # 상대축은 anchor 0
    def _target(kind, tgt, axis):
        if kind == "corner":                       # row→height, col→width (H-1 / W-1)
            return f"{'height' if axis == 'row' else 'width'}(input_grid) - 1"
        return str(tgt)                            # rel Δ / abs v / br v / edge 0
    ar, ac = _anchor(r[2], "row"), _anchor(c[2], "col")
    tr, tc = _target(r[0], r[1], "row"), _target(c[0], c[1], "col")
    # 두 축 anchor 종류 같으면 whole-point 형태(top_left(obj)/bottom_right(obj))
    if r[2] == c[2] and r[2] in ("tl", "br"):
        whole = "top_left" if r[2] == "tl" else "bottom_right"
        return f"{coord} - {whole}({objvar}) + ({tr}, {tc})"
    # 혼합: 성분별 anchor
    return f"{coord} - ({ar}, {ac}) + ({tr}, {tc})"


def _split_move(resolved_val):
    """'move[ROW,COL]@sel' → (row_tok, col_tok, sel). 파싱 실패 시 (None,None,None)."""
    m = re.match(r"^move\[(.+?),(.+?)\](?:@(.+))?$", resolved_val)
    if not m:
        return None, None, None
    return m.group(1), m.group(2), (m.group(3) or None)


def _strip_vspace(sel):
    """선택자 뒤에 붙는 version-space 가설 인덱스 suffix('...#k', k=정수) 제거 — 모호(K>1)할 때만
    resolve 가 전체 이름 끝에 최종 '#k' 를 덧붙인다(arbor/reasoning/antiunify.py `_push`/`resolve_slot`,
    §2026-07-20 조사). `shape#N` 은 그 자체가 base 선택자 이름(N=shape class index)이라 보존 —
    'shape#0#1' 처럼 뒤에 또 버전 suffix 가 붙은 경우만 그 마지막 '#k' 를 벗긴다."""
    m = re.match(r"^shape#\d+#\d+$", sel)
    if m:
        return sel.rsplit("#", 1)[0]
    if not sel.startswith("shape#") and re.match(r"^.+#\d+$", sel):
        return sel.rsplit("#", 1)[0]
    return sel


def _sel_of(resolved_val):
    """resolved 값의 @선택자 ('move[..]@color=2'→'color=2', 'color@bounded'→'bounded').
    version-space suffix('@bounded#0'→'bounded')는 _strip_vspace 로 제거."""
    sel = resolved_val.rsplit("@", 1)[1] if "@" in resolved_val else None
    return _strip_vspace(sel) if sel else sel


def render_solution_lines(solution_ast, resolved, comm, shapes):
    """설계 §5 형태의 표시줄 리스트. 시각화-먼저(솔버 데이터 재표기). 결정적."""
    body = solution_ast.get("body") or []
    parts = {s["call"]: s["args"] for s in body}
    # 1) 공통 선택자 → 객체 바인딩 obj0 (선택자-일관: 모든 슬롯 동일 @sel)
    sel = next((_sel_of(v) for v in resolved.values() if _sel_of(v)), None)
    cond, shape_ref = selector_to_condition(sel)
    lines = []
    if shape_ref is not None:
        lines.append(f"{shape_ref} = {shapes.get(shape_ref, '[]')}")
    lines.append(f"obj0 = select(object, {cond})")
    objvar = "obj0"
    var_i = [0]

    def _new_var():
        var_i[0] += 1
        return f"?var{var_i[0]}"

    # 2) set_grid_size (COMM→리터럴, DIFF→변수화)
    sz = parts["set_grid_size"]["size"]
    if comm.get("size", True):
        v = sz.get("const")
        if isinstance(v, dict):
            lit = f"({v.get('height')}, {v.get('width')})"
        elif v is not None:
            lit = str(v)
        else:
            lit = str(sz.get("expr"))                 # const 없음(예: size(input_grid)) → expr fallback
        lines.append(f"set_grid_size = {lit}")
    else:
        vn = _new_var(); lines.append(f"{vn} = size(input_grid)")
        lines.append(f"set_grid_size = {vn}")
    # 3) set_grid_color
    co = parts["set_grid_color"]["color"]
    if comm.get("color", True):
        lines.append(f"set_grid_color = {co.get('const', co.get('expr'))}")
    else:
        vn = _new_var(); lines.append(f"{vn} = color(input_grid)")
        lines.append(f"set_grid_color = {vn}")
    # 4) coloring 스텝 (cellset=DIFF 슬롯 → 변수화; color=const→리터럴/var→color(obj))
    prog = parts["set_grid_contents"]["contents"].get("program", {}).get("body", [])
    for s in prog:
        tgt = s["args"]["target"]; colr = s["args"]["color"]
        cell_var = tgt.get("cells", {}).get("var") if tgt.get("ref") == "cellset" else None
        # 좌표 변수
        if cell_var and cell_var in resolved:
            rt, ct, _ = _split_move(resolved[cell_var])
            expr = move_to_vector(rt, ct, objvar) if rt else f"coordinate({objvar})"
        else:
            expr = f"coordinate({objvar})"
        vcoord = _new_var(); lines.append(f"{vcoord} = {expr}")
        # 색
        if "const" in colr:
            cterm = str(colr["const"])
        else:
            vcol = _new_var(); lines.append(f"{vcol} = color({objvar})")
            cterm = vcol
        lines.append(f"coloring({vcoord}, {cterm})")
    return lines
