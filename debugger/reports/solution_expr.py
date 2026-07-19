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
    # 둘 다 격자코너
    if r[0] == "corner" and c[0] == "corner":
        return f"{coord} - bottom_right({objvar}) + bottom_right(input_grid)"
    # 앵커 성분(각 축)과 target 성분
    def _anchor(comp, axis):                       # axis: 'r'|'c'
        if comp == "tl":
            return f"top_left({objvar}).{axis}"
        if comp == "br":
            return f"bottom_right({objvar}).{axis}"
        return "0"                                 # 상대축은 anchor 0
    def _target(kind, tgt, axis):
        if kind == "corner":
            return f"bottom_right(input_grid).{axis}"
        return str(tgt)                            # rel Δ / abs v / br v / edge 0
    ar, ac = _anchor(r[2], "row"), _anchor(c[2], "col")
    tr, tc = _target(r[0], r[1], "row"), _target(c[0], c[1], "col")
    # 두 축 anchor 종류 같으면 whole-point 형태(top_left(obj)/bottom_right(obj))
    if r[2] == c[2] and r[2] in ("tl", "br"):
        whole = "top_left" if r[2] == "tl" else "bottom_right"
        return f"{coord} - {whole}({objvar}) + ({tr}, {tc})"
    # 혼합: 성분별 anchor
    return f"{coord} - ({ar}, {ac}) + ({tr}, {tc})"
