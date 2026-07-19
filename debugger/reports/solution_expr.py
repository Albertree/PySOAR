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
